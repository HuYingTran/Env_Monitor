# 🌡️ Env Monitor

Hệ thống web giám sát **nhiệt độ / độ ẩm / áp suất** trong nhà kho theo thời gian
thực. Mỗi kho có **bản đồ sơ đồ** với vùng và vị trí cảm biến, cảnh báo theo
ngưỡng, xem lịch sử và xuất Excel, phân quyền người dùng.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?logo=flask)
![InfluxDB](https://img.shields.io/badge/InfluxDB-2.x-22ADF6?logo=influxdb&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)

## ✨ Tính năng

- **Trang chủ** dạng tab, mỗi tab là một kho.
- **Bản đồ kho**: upload ảnh sơ đồ, vẽ vùng, đặt marker cảm biến (kéo thả), marker đổi màu theo trạng thái
  (🟢 bình thường · 🟡 cảnh báo · 🔴 nguy hiểm · ⚪ chưa có dữ liệu).
- **Lịch sử** dữ liệu đo, **xuất Excel**.
- **Thiết bị & cảm biến**: quản lý, cấu hình ngưỡng; **tự phát hiện cảm biến mới** đang gửi dữ liệu lên InfluxDB.
- **Người dùng & phân quyền**: `admin`, `manager`, `viewer`.
- **Cài đặt** trang web, trang **đăng nhập**.
- Script **mô phỏng dữ liệu** cho các cảm biến đã đăng ký.

## 🏗️ Kiến trúc

```
Cảm biến ──► InfluxDB (time-series: nhiệt độ, độ ẩm, áp suất)
                 │
                 ▼
            Flask app ◄──► SQLite (kho, vùng, cảm biến, thiết bị, user, cài đặt)
                 │
                 ▼
            Trình duyệt
```

Schema InfluxDB giả định (chỉnh trong `app/influx_client.py` nếu khác):

| Thành phần | Giá trị |
|---|---|
| measurement | `temperature` |
| tag | `sensor_code` (khớp "Mã cảm biến" trên bản đồ kho) |
| field | `value` |

## 🚀 Cài đặt & chạy

```bash
git clone https://github.com/HuYingTran/Env_Monitor.git
cd Env_Monitor

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env     # điền INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET, FLASK_SECRET_KEY

python seed.py           # tạo bảng SQLite + tài khoản admin mặc định
python run.py            # http://127.0.0.1:5004
```

Đăng nhập bằng `admin` / `admin123` rồi **đổi mật khẩu ngay** trong trang Cài đặt / Người dùng.

> Nếu chưa cấu hình InfluxDB, ứng dụng vẫn chạy nhưng dữ liệu hiển thị "Không có dữ liệu".

### Biến môi trường (`.env`)

| Biến | Ý nghĩa |
|---|---|
| `FLASK_SECRET_KEY` | Secret key cho session |
| `FLASK_DEBUG` | Bật chế độ debug (`1`/`0`) |
| `DATABASE_URL` | SQLite, mặc định `sqlite:///../instance/env_monitor.db` |
| `INFLUX_URL` / `INFLUX_TOKEN` / `INFLUX_ORG` / `INFLUX_BUCKET` | Kết nối InfluxDB |

## 👥 Vai trò người dùng

| Vai trò | Quyền |
|---|---|
| `admin` | Toàn quyền, gồm quản lý user và cài đặt trang web |
| `manager` | Quản lý kho, bản đồ kho, cảm biến, thiết bị |
| `viewer` | Chỉ xem trang chủ và lịch sử |

## 🧪 Mô phỏng dữ liệu cảm biến

Script đọc danh sách cảm biến **đã đăng ký** trong SQLite và ghi dữ liệu giả vào InfluxDB:

```bash
python simulate_devices.py                # ghi mỗi 5s, Ctrl+C để dừng
python simulate_devices.py --once         # ghi 1 lần
python simulate_devices.py --interval 2   # đổi chu kỳ ghi
```

Đại lượng đo suy ra từ tiền tố mã cảm biến:

| Tiền tố | Đo |
|---|---|
| `T-xxxx` | Nhiệt độ |
| `TH-xxxx` | Nhiệt độ + độ ẩm |
| `THP-xxxx` | Nhiệt độ + độ ẩm + áp suất |

Baseline nhiệt độ tự bám theo ngưỡng cảnh báo đã đặt cho từng cảm biến.

## 🗺️ Sử dụng bản đồ kho

Vào chi tiết một kho → (admin/manager) bật **"Chế độ chỉnh sửa"**:

- **Thêm vùng**: kéo chuột trên ảnh sơ đồ, đặt tên và màu.
- **Thêm cảm biến**: click vào vị trí trên ảnh, nhập tên + mã cảm biến (khớp tag `sensor_code`).
- **Di chuyển**: kéo thả vùng hoặc marker.
- **Xóa**: icon thùng rác ở góc vùng; mở marker rồi bấm "Xóa cảm biến".
- Ngoài chế độ chỉnh sửa: click marker để xem giá trị mới nhất.

### Tự động phát hiện cảm biến mới

Trang **Thiết bị** quét InfluxDB (24h gần nhất) mỗi lần tải trang, tìm các `sensor_code`
đang gửi dữ liệu nhưng chưa được đăng ký và hiện banner **"Phát hiện N cảm biến mới"** kèm nút
**Đăng ký**. Cảm biến chưa có tọa độ được gắn nhãn **"Chưa đặt vị trí"** — vào bản đồ kho, bật chế
độ chỉnh sửa, chọn cảm biến trong dropdown **"Đặt vị trí cảm biến đã đăng ký"** rồi click lên bản đồ.

## 📁 Cấu trúc thư mục

```
Env_Monitor/
├── run.py                 # entrypoint (port 5004)
├── seed.py                # tạo bảng + admin mặc định
├── simulate_devices.py    # mô phỏng dữ liệu cảm biến
├── config.py
├── requirements.txt
├── .env.example
└── app/
    ├── models.py          # Role, User, Warehouse, Zone, Sensor, Device, SiteSetting
    ├── influx_client.py   # truy vấn InfluxDB (Flux)
    ├── decorators.py      # roles_required(*roles)
    ├── auth/ main/ reports/ devices/ users/ settings/   # blueprints
    ├── templates/
    └── static/            # css, js (warehouse_map.js), uploads/
```

> Bảng SQLite đang được tạo bằng `db.create_all()` trong `seed.py`. Khi cần quản lý
> thay đổi schema, có thể dùng Flask-Migrate: `flask db init && flask db migrate && flask db upgrade`.
