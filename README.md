# Chatbot LangChain + FastAPI

Ứng dụng Chatbot kết hợp LangChain, FastAPI, FAISS vector DB, cho phép xử lý dữ liệu văn bản, PDF, đông thời cung cấp các tính năng quản trị có phân quyền (Tài khoản, Lịch sử hoạt động, Lịch sử chatbot, Cài đặt).

---
## Git clone
```bash
git clone https://github.com/hodaketech/LangChain-Chatbot.git
```

### Thiết lập các API tại config.py:

## 📦 1. Chạy Local

### ▶️ Cài đặt dependencies:
```
pip install -r requirements.txt
```

### ▶️ Chạy ứng dụng bằng Uvicorn:
```
uvicorn app.api:app --reload --port 8000
```

Ứng dụng sẽ khởi chạy tại:

```
http://localhost:8000
```

---

## 🐳 2. Triển khai bằng Docker

### ✅ Lưu ý:
- Tăng `--workers` trong dòng `CMD` của Dockerfile theo đúng số core CPU máy chủ.
- Nếu dùng reverse proxy như **Nginx**, cần bổ sung service trong `docker-compose.yml`.

---

### 🔨 Build image:
```
docker build -t chatbot-langchain .
```

### ▶️ Chạy container:
```
docker run -d -p 8000:8000 --name chatbot_test chatbot-langchain
```

Người dùng có thể truy cập qua trình duyệt tại:

```
http://<IP-của-server>:8000
```
```
http://localhost:8000
```
---

### 🔁 Dừng container:
```
docker stop chatbot_test
```

### 🔁 Khởi động lại:
```
docker start chatbot_test
```

---

### 💾 Backup dữ liệu:

Ứng dụng sử dụng thư mục `./persistent/` để lưu backup trong trường hợp docker bị remove:

```
persistent/
├── data.db
├── chat.db
└── vectorstores/
```
