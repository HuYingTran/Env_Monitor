"""Wrapper truy vấn InfluxDB cho dữ liệu nhiệt độ.

Schema giả định (chỉnh sửa các Flux query bên dưới nếu schema thật khác):
  measurement: temperature
  tag:         sensor_code
  field:       value
"""

import logging

from flask import current_app
from influxdb_client import InfluxDBClient
from influxdb_client.client.exceptions import InfluxDBError

logger = logging.getLogger(__name__)

MEASUREMENT = "temperature"
FIELD = "value"
TAG_SENSOR_CODE = "sensor_code"


def _get_client():
    cfg = current_app.config
    if not cfg.get("INFLUX_URL") or not cfg.get("INFLUX_TOKEN") or not cfg.get("INFLUX_ORG"):
        return None
    try:
        return InfluxDBClient(url=cfg["INFLUX_URL"], token=cfg["INFLUX_TOKEN"], org=cfg["INFLUX_ORG"], timeout=5000)
    except Exception:
        logger.exception("Không thể tạo InfluxDB client")
        return None


def get_latest_reading(sensor_code):
    """Trả về dict {value, time} hoặc None nếu không có dữ liệu / không kết nối được."""
    client = _get_client()
    if client is None:
        return None
    bucket = current_app.config["INFLUX_BUCKET"]
    query = f'''
    from(bucket: "{bucket}")
      |> range(start: -7d)
      |> filter(fn: (r) => r._measurement == "{MEASUREMENT}" and r._field == "{FIELD}")
      |> filter(fn: (r) => r["{TAG_SENSOR_CODE}"] == "{sensor_code}")
      |> last()
    '''
    try:
        with client:
            tables = client.query_api().query(query)
        for table in tables:
            for record in table.records:
                return {"value": record.get_value(), "time": record.get_time()}
        return None
    except InfluxDBError:
        logger.exception("Lỗi truy vấn InfluxDB (get_latest_reading)")
        return None
    except Exception:
        logger.exception("Không thể kết nối InfluxDB (get_latest_reading)")
        return None


def get_readings_range(sensor_code, start, stop, measurement=MEASUREMENT):
    """Trả về list [{value, time}, ...] trong khoảng [start, stop] (ISO 8601 hoặc Flux duration).

    measurement: "temperature" (mặc định), "humidity" hoặc "pressure".
    """
    client = _get_client()
    if client is None:
        return []
    bucket = current_app.config["INFLUX_BUCKET"]
    query = f'''
    from(bucket: "{bucket}")
      |> range(start: {start}, stop: {stop})
      |> filter(fn: (r) => r._measurement == "{measurement}" and r._field == "{FIELD}")
      |> filter(fn: (r) => r["{TAG_SENSOR_CODE}"] == "{sensor_code}")
      |> sort(columns: ["_time"])
    '''
    try:
        with client:
            tables = client.query_api().query(query)
        readings = []
        for table in tables:
            for record in table.records:
                readings.append({"value": record.get_value(), "time": record.get_time()})
        return readings
    except InfluxDBError:
        logger.exception("Lỗi truy vấn InfluxDB (get_readings_range)")
        return []
    except Exception:
        logger.exception("Không thể kết nối InfluxDB (get_readings_range)")
        return []


def get_readings_range_multi(sensor_codes, start, stop, measurement=MEASUREMENT, every=None):
    """Truy vấn nhiều sensor_code cùng lúc trong 1 query (tránh N truy vấn riêng lẻ).

    every: nếu có (vd "60s"), downsample bằng aggregateWindow(mean) để giới hạn
    số điểm trả về khi xem khoảng thời gian dài.

    Trả về dict {sensor_code: [{value, time}, ...]}.
    """
    result = {code: [] for code in sensor_codes}
    if not sensor_codes:
        return result
    client = _get_client()
    if client is None:
        return result
    bucket = current_app.config["INFLUX_BUCKET"]
    codes_literal = "[" + ", ".join(f'"{code}"' for code in sensor_codes) + "]"
    aggregate_clause = f'|> aggregateWindow(every: {every}, fn: mean, createEmpty: false)' if every else ""
    query = f'''
    from(bucket: "{bucket}")
      |> range(start: {start}, stop: {stop})
      |> filter(fn: (r) => r._measurement == "{measurement}" and r._field == "{FIELD}")
      |> filter(fn: (r) => contains(value: r["{TAG_SENSOR_CODE}"], set: {codes_literal}))
      {aggregate_clause}
      |> sort(columns: ["_time"])
    '''
    try:
        with client:
            tables = client.query_api().query(query)
        for table in tables:
            for record in table.records:
                code = record.values.get(TAG_SENSOR_CODE)
                if code in result:
                    result[code].append({"value": record.get_value(), "time": record.get_time()})
        return result
    except InfluxDBError:
        logger.exception("Lỗi truy vấn InfluxDB (get_readings_range_multi)")
        return result
    except Exception:
        logger.exception("Không thể kết nối InfluxDB (get_readings_range_multi)")
        return result


def get_recent_sensor_codes(lookback="-24h"):
    """Trả về tập hợp sensor_code đã gửi dữ liệu trong khoảng lookback (dùng để phát hiện thiết bị mới)."""
    client = _get_client()
    if client is None:
        return set()
    bucket = current_app.config["INFLUX_BUCKET"]
    query = f'''
    import "influxdata/influxdb/schema"
    schema.tagValues(bucket: "{bucket}", tag: "{TAG_SENSOR_CODE}", predicate: (r) => r._measurement == "{MEASUREMENT}", start: {lookback})
    '''
    try:
        with client:
            tables = client.query_api().query(query)
        codes = set()
        for table in tables:
            for record in table.records:
                value = record.get_value()
                if value:
                    codes.add(value)
        return codes
    except InfluxDBError:
        logger.exception("Lỗi truy vấn InfluxDB (get_recent_sensor_codes)")
        return set()
    except Exception:
        logger.exception("Không thể kết nối InfluxDB (get_recent_sensor_codes)")
        return set()


def is_configured():
    cfg = current_app.config
    return bool(cfg.get("INFLUX_URL") and cfg.get("INFLUX_TOKEN") and cfg.get("INFLUX_ORG"))
