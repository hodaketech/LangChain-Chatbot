import asyncio
import aiosqlite
from itsdangerous import URLSafeSerializer
from datetime import datetime
import os
from app.config import ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_NAME

# Define the path for the user database
DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")
SECRET_KEY = "f9a37e1f27a748ad893c7a682c2a711dcfbef2d3e9092e7a189f587fd7329a02"
serializer = URLSafeSerializer(SECRET_KEY)

# Initialize the user database and create the user and activity tables if they don't exist
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mail TEXT UNIQUE,
                password TEXT,
                name TEXT,
                role INTEGER,
                create_at TEXT
            );
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                description TEXT,
                time TEXT,
                FOREIGN KEY(user_id) REFERENCES user(id)
            );
        """)
        await db.commit()
    
        # Gọi kiểm tra admin mặc định
        await ensure_default_admin()

# Call this function at the start of your application to ensure the database is ready
async def login(email: str, password: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, name, role FROM user WHERE mail = ? AND password = ?", (email, password))
        row = await cursor.fetchone()
        if row:
            user_id, name, role = row
            token = serializer.dumps({"user_id": user_id, "name": name, "role": role})
            await db.execute("INSERT INTO activity (user_id, description, time) VALUES (?, ?, ?)",
                             (user_id, "Đăng nhập thành công", datetime.now().isoformat()))
            await db.commit()
            return token, name, role
        return None, None, None

# Ensure the default admin account exists
async def ensure_default_admin():
    """
    Đảm bảo rằng tài khoản admin mặc định luôn tồn tại và đúng thông tin trong config.
    Nếu đã tồn tại → cập nhật lại mật khẩu, tên và role = 1.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id FROM user WHERE mail = ?", (ADMIN_EMAIL,))
        row = await cursor.fetchone()

        if row:
            # Cập nhật lại tài khoản mặc định theo config
            user_id = row[0]
            await db.execute("""
                UPDATE user
                SET password = ?, name = ?, role = 1
                WHERE id = ?
            """, (ADMIN_PASSWORD, ADMIN_NAME, user_id))
            print("🔄 Cập nhật tài khoản admin mặc định theo config.")
        else:
            # Tạo mới tài khoản admin mặc định
            await db.execute("""
                INSERT INTO user (mail, password, name, role, create_at)
                VALUES (?, ?, ?, ?, ?)
            """, (ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_NAME, 1, datetime.now().isoformat()))
            print("✅ Tạo mới tài khoản admin mặc định.")

        await db.commit()

# Decode the token to get user information
def decode_token(token: str):
    try:
        return serializer.loads(token)
    except:
        return None

# ───── CRUD USER ─────
async def create_user(mail, password, name, role):
    async with aiosqlite.connect(DB_PATH) as db:
        # Kiểm tra email đã tồn tại chưa
        cursor = await db.execute("SELECT id FROM user WHERE mail = ?", (mail,))
        row = await cursor.fetchone()
        if row:
            return False  # Email đã tồn tại
        try:
            await db.execute(
                "INSERT INTO user (mail, password, name, role, create_at) VALUES (?, ?, ?, ?, ?)", 
                (mail, password, name, role, datetime.now().isoformat())
            )
            await db.commit()
            return True
        except Exception as e:
            return False

async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, mail, name, role, create_at FROM user")
        return await cursor.fetchall()

async def delete_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM user WHERE id = ?", (user_id,))
        await db.commit()

async def update_user(user_id, role=None, password=None):
    async with aiosqlite.connect(DB_PATH) as db:
        if password is not None:
            await db.execute("UPDATE user SET password = ? WHERE id = ?", (password, user_id))
        if role is not None:
            await db.execute("UPDATE user SET role = ? WHERE id = ?", (role, user_id))
        await db.commit()

async def get_user_id_by_mail_and_name(mail, name):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id FROM user WHERE mail = ? AND name = ?", (mail, name))
        row = await cursor.fetchone()
        return row[0] if row else None

# ───── CRUD ACTIVITY ─────
async def get_user_activities(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, description, time FROM activity WHERE user_id = ? ORDER BY time DESC", (user_id,))
        return await cursor.fetchall()
    
async def create_activity(user_id: int, description: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO activity (user_id, description, time) VALUES (?, ?, ?)",
            (user_id, description, datetime.now().isoformat())
        )
        await db.commit()

if __name__ == "__main__":
    # Example usage
    async def test():
        await init_db()
        print("📋 Danh sách user:")
        users = await get_all_users()
        for u in users:
            print(u)
        print("🔑 Thử login...")
        token, name, role = await login("admin@a.com", "123456")
        if token:
            print(f"✅ Đăng nhập thành công: {name}, Role: {role}")
            print("🧾 Token:", token)
            decoded = decode_token(token)
            print("🔍 Decode token:", decoded)
        else:
            print("❌ Sai thông tin đăng nhập.")

    asyncio.run(test())