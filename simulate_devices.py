"""Mô phỏng dữ liệu gửi vào InfluxDB cho các cảm biến ĐÃ ĐĂNG KÝ thật trong hệ thống.

Khác với bản trước (tự sinh N thiết bị giả theo tiền tố cố định), script này
đọc trực tiếp danh sách Sensor trong database (SQLite) — dùng đúng sensor_code
đã đăng ký qua web, không tạo mã giả không tồn tại.

Đo đại lượng nào cho từng cảm biến được suy ra từ tiền tố mã:
  T-xxxx    : chỉ đo nhiệt độ
  TH-xxxx   : đo nhiệt độ + độ ẩm
  THP-xxxx  : đo nhiệt độ + độ ẩm + áp suất
  (mã khác không theo quy ước trên) : mặc định chỉ đo nhiệt độ

Mỗi đại lượng ghi vào 1 measurement riêng (temperature/humidity/pressure),
field "value", tag "sensor_code" — measurement "temperature" khớp đúng schema
mà app/influx_client.py đang đọc (xem README).

Baseline nhiệt độ tính theo ngưỡng cảnh báo của từng cảm biến (nếu có đặt) để
dữ liệu mô phỏng bám sát cấu hình thật, thay vì random hoàn toàn.

Chạy:
    python simulate_devices.py                  # ghi mỗi 5s, chạy tới khi Ctrl+C
    python simulate_devices.py --interval 2      # đổi chu kỳ ghi
    python simulate_devices.py --once            # chỉ ghi 1 lần rồi thoát

Chưa có cảm biến nào trong hệ thống? Vào web đăng ký/tạo cảm biến trước
(trang Thiết bị hoặc bản đồ kho), script sẽ tự động dùng đúng danh sách đó.
"""

import argparse
import random
import time
from datetime import datetime, timezone

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.exceptions import InfluxDBError
from influxdb_client.client.write_api import SYNCHRONOUS

from app import create_app
from app.models import Sensor

FIELD = "value"
TAG_SENSOR_CODE = "sensor_code"

RANGES = {
    "temperature": {"min": 15.0, "max": 45.0, "step": 0.5},
    "humidity": {"min": 20.0, "max": 95.0, "step": 1.5},
    "pressure": {"min": 990.0, "max": 1030.0, "step": 0.8},
}

DEFAULT_TEMPERATURE_BASELINE = 22.0


def measurements_for_code(sensor_code):
    if sensor_code.startswith("THP-"):
        return ["temperature", "humidity", "pressure"]
    if sensor_code.startswith("TH-"):
        return ["temperature", "humidity"]
    return ["temperature"]


def load_sensors_from_db(app):
    """Đọc danh sách Sensor thật từ SQLite, trả về list [{code, name, warning_threshold}, ...]."""
    with app.app_context():
        sensors = Sensor.query.order_by(Sensor.sensor_code).all()
        return [
            {
                "code": s.sensor_code,
                "name": s.name,
                "warning_threshold": s.warning_threshold,
            }
            for s in sensors
        ]


def build_state(sensors):
    """Trả về dict: sensor_code -> {measurement: giá trị hiện tại}."""
    state = {}
    for s in sensors:
        measurements = measurements_for_code(s["code"])
        values = {}
        for m in measurements:
            if m == "temperature":
                # bám theo ngưỡng cảnh báo thật nếu có đặt, để phần lớn thời gian ở mức bình thường
                baseline = (s["warning_threshold"] - 6) if s["warning_threshold"] is not None else DEFAULT_TEMPERATURE_BASELINE
                baseline = max(RANGES["temperature"]["min"], min(RANGES["temperature"]["max"], baseline))
            else:
                r = RANGES[m]
                baseline = random.uniform(r["min"], r["max"])
            values[m] = float(baseline)
        state[s["code"]] = values
    return state


def next_value(state, code, measurement):
    r = RANGES[measurement]
    delta = random.uniform(-r["step"], r["step"])
    value = max(r["min"], min(r["max"], state[code][measurement] + delta))
    state[code][measurement] = value
    return round(value, 2)


def write_once(write_api, bucket, state):
    points = []
    for code, values in state.items():
        readings = []
        for measurement in values:
            value = next_value(state, code, measurement)
            point = (
                Point(measurement)
                .tag(TAG_SENSOR_CODE, code)
                .field(FIELD, value)
                .time(datetime.now(timezone.utc))
            )
            points.append(point)
            readings.append(f"{measurement}={value}")
        print(f"  {code}: " + ", ".join(readings))
    write_api.write(bucket=bucket, record=points)
    print(f"-> Đã ghi {len(points)} điểm dữ liệu lúc {datetime.now().strftime('%H:%M:%S')}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--interval", type=float, default=5, help="Chu kỳ ghi (giây), mặc định 5s")
    parser.add_argument("--once", action="store_true", help="Chỉ ghi 1 lần rồi thoát")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        influx_url = app.config["INFLUX_URL"]
        influx_token = app.config["INFLUX_TOKEN"]
        influx_org = app.config["INFLUX_ORG"]
        influx_bucket = app.config["INFLUX_BUCKET"]

    if not (influx_url and influx_token and influx_org and influx_bucket):
        print("Thiếu cấu hình InfluxDB trong .env (INFLUX_URL / INFLUX_TOKEN / INFLUX_ORG / INFLUX_BUCKET).")
        return

    sensors = load_sensors_from_db(app)
    if not sensors:
        print("Chưa có cảm biến nào được đăng ký trong hệ thống. Vào web tạo cảm biến trước, rồi chạy lại script này.")
        return

    state = build_state(sensors)
    client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    print(f"Mô phỏng {len(sensors)} cảm biến đã đăng ký thật trong hệ thống:")
    for code, values in state.items():
        print(f"  {code}: đo {', '.join(values)}")
    print(f"Ghi vào bucket '{influx_bucket}' tại {influx_url}" + (" (1 lần)" if args.once else f", mỗi {args.interval}s. Ctrl+C để dừng."))

    try:
        while True:
            try:
                write_once(write_api, influx_bucket, state)
            except InfluxDBError as exc:
                print(f"Lỗi ghi InfluxDB: {exc}")
            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nĐã dừng mô phỏng.")
    finally:
        write_api.close()
        client.close()


if __name__ == "__main__":
    main()
