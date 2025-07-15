from fastapi import FastAPI, Form, File, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, RedirectResponse
from pydantic import BaseModel
import os
import shutil
from datetime import datetime
import json
import aiosqlite
import glob
import app.config as config
from app.qabot import read_vectors_db, load_llm, create_prompt, create_qa_chain
from app.prepare_vector_db import create_db_from_text, create_db_from_files, delete_document_by_id, clean_faiss_database
from app.prepare_vector_db import semantic_search_with_similarity
from app.config import TEMPLATE, PDF_DATA_PATH
from app.database_user import login as db_login, get_all_users, update_user, delete_user
from app.database_user import get_user_id_by_mail_and_name, create_activity, create_user, get_user_activities
from app.database_chat import save_chat, get_chat_history, init_chat_db
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_chat_db()
    yield

# === FastAPI Init ===
app = FastAPI(lifespan=lifespan)

# === Middleware ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session middleware for user sessions
app.add_middleware(
    SessionMiddleware,
    secret_key="79ac98c70bafb4358e164504a3b137da10afca183b1b74287b12c6a47b6129c6",
    session_cookie="sessionid"
)

# === Static files ===
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")),
    name="static"
)

# === Ensure PDF data directory exists ===
if not os.path.exists(PDF_DATA_PATH):
    os.makedirs(PDF_DATA_PATH)

# === Chatbot Components ===
db = read_vectors_db()
llm = load_llm()
prompt = create_prompt(TEMPLATE)
qa_chain = create_qa_chain(prompt, llm, db)
_last_reload_time = 0

# === Reload Flag ===
# This file is used to trigger a reload of the QA chain when it is modified.
RELOAD_FLAG_PATH = "app/reload_flag.txt"

# Ensure the reload flag file exists
def touch_reload_flag():
    with open(RELOAD_FLAG_PATH, "w") as f:
        f.write(str(datetime.now().timestamp()))

# Check if the reload flag file exists and update the last reload time
def maybe_reload_qa_chain():
    global qa_chain, db, _last_reload_time
    try:
        mtime = os.path.getmtime(RELOAD_FLAG_PATH)
        if mtime > _last_reload_time:
            _last_reload_time = mtime
            db = read_vectors_db()
            qa_chain = create_qa_chain(prompt, llm, db)
    except FileNotFoundError:
        pass

# === Models ===
class QuestionRequest(BaseModel):
    question: str

# === Activity Logging ===
async def log_activity(request: Request, description: str):
    user = request.session.get("user")
    if not user:
        return
    user_id = await get_user_id_by_mail_and_name(user["mail"], user["name"])
    if user_id:
        await create_activity(user_id, description)

# === Clear Data foulder ===
def delete_all_pdfs_in_data():
    folder_path = PDF_DATA_PATH
    pdf_files = glob.glob(os.path.join(folder_path, '*.pdf'))

    for pdf_file in pdf_files:
        try:
            os.remove(pdf_file)
            print(f"Đã xoá: {pdf_file}")
        except Exception as e:
            print(f"Lỗi khi xoá {pdf_file}: {e}")

# === Routes ===
@app.get("/")
async def root(request: Request):
    file_name = "home.html" if request.session.get("user") else "login.html"
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", file_name))

#  Redirect to home page
@app.get("/static/home.html")
async def home_page(request: Request):
    if not request.session.get("user"):
        return FileResponse(os.path.join(os.path.dirname(__file__), "static", "login.html"))
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "home.html"))

#  Redirect to login page
@app.post("/ask")
async def ask_question(req: QuestionRequest):
    maybe_reload_qa_chain()
    result = qa_chain.invoke({"query": req.question})
    answer = result["result"]
    sources_text = "\n".join([doc.page_content.strip() for doc in result["source_documents"]])
    await save_chat(req.question, answer, sources_text)
    return {
        "answer": answer,
        "sources": [doc.page_content.strip() for doc in result["source_documents"]]
    }

#  Redirect to chat history page
@app.get("/api/chat-history")
async def api_chat_history(
    request: Request,
    order: str = "desc",
    limit: int = 10,
    start_date: str = None,
    end_date: str = None
):
    history = await get_chat_history(order, limit, start_date, end_date)
    return JSONResponse(history)

#  Upload and process text to faiss database
@app.post("/process-text")
async def process_text(text: str = Form(...), request: Request = None):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        text_filename = f"{PDF_DATA_PATH}/text_{timestamp}.txt"
        with open(text_filename, "w", encoding="utf-8") as f:
            f.write(text)
        create_db_from_text(text)
        touch_reload_flag()
        if request:
            await log_activity(request, f"Xử lý văn bản: {text_filename}")
        return JSONResponse(status_code=200, content={"message": "Xử lý văn bản thành công"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

#  Upload and process pdf file to faiss database
@app.post("/process-pdf")
async def process_pdf(pdf: UploadFile = File(...), request: Request = None):
    try:
        # Xoá tất cả PDF cũ, ngoại trừ file đang upload
        delete_all_pdfs_in_data()
        #Lưu file PDF vào thư mục
        pdf_path = f"{PDF_DATA_PATH}/{pdf.filename}"
        with open(pdf_path, "wb") as f:
            shutil.copyfileobj(pdf.file, f)
        create_db_from_files()
        touch_reload_flag()
        if request:
            await log_activity(request, f"Xử lý PDF: {pdf.filename}")
        return JSONResponse(content={"message": "Xử lý PDF thành công"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

#  Semantic search endpoint to delete document by ID
@app.post("/semantic-search")
async def semantic_search(req: QuestionRequest):
    output = semantic_search_with_similarity(req.question, top_k=10)
    return {"result": output}

#  Delete document by ID
@app.post("/delete-document")
async def delete_document(request: Request):
    try:
        data = await request.json()
        doc_id = data.get('doc_id')
        if not doc_id:
            return Response(content="Missing document ID", media_type="text/plain", status_code=400)
        success, message = delete_document_by_id(doc_id)
        if success:
            touch_reload_flag()
            await log_activity(request, f"Xoá tài liệu doc_id={doc_id}")
        return Response(content=message, media_type="text/plain", status_code=200 if success else 400)
    except Exception as e:
        return Response(content=f"Error: {str(e)}", media_type="text/plain", status_code=500)

#  Get configuration settings
@app.get("/get-config")
async def get_config():
    try:
        config_data = {
            "OPENAI_API_KEY": config.OPENAI_API_KEY,
            "GOOGLE_API_KEY": config.GOOGLE_API_KEY,
            "EMBEDDING_MODEL": config.EMBEDDING_MODEL,
            "EMBEDDING_DIMENSION": config.EMBEDDING_DIMENSION,
            "LLM_MODEL": config.LLM_MODEL,
            "CHUNK_SIZE": config.CHUNK_SIZE,
            "CHUNK_OVERLAP": config.CHUNK_OVERLAP,
            "RETRIEVER_K": config.RETRIEVER_K,
            "TEMPLATE": config.TEMPLATE
        }
        return JSONResponse(content=config_data)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

#  Update configuration settings
@app.post("/update-config")
async def update_config(settings: dict, request: Request):
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'config.py')
        # Đọc config cũ
        old_config = {}
        with open(config_path, 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line:
                    key, val = line.split('=', 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    old_config[key] = val

        updated_lines = []
        changed_keys = []
        with open(config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for line in lines:
            updated = False
            for key, value in settings.items():
                if line.startswith(key + " ="):
                    old_val = old_config.get(key)
                    # So sánh giá trị cũ và mới (chuyển về str để so sánh)
                    if str(old_val) != str(value):
                        changed_keys.append(f"{key}: {old_val} → {value}")
                    # Cập nhật dòng
                    if isinstance(value, str):
                        line = f'{key} = "{value}"\n'
                    else:
                        line = f'{key} = {value}\n'
                    updated = True
            updated_lines.append(line)
        with open(config_path, 'w', encoding='utf-8') as f:
            f.writelines(updated_lines)
        # Chỉ log các key thực sự thay đổi
        if changed_keys:
            await log_activity(request, "Cập nhật config: " + "; ".join(changed_keys))
        return JSONResponse(content={"message": "Settings updated successfully"})
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

#  Clean FAISS database
@app.post("/clean-faiss-db")
async def clean_faiss_db(request: Request):
    try:
        ok = clean_faiss_database()
        if ok:
            await log_activity(request, "Làm sạch FAISS database")
            return JSONResponse(content={"message": "Đã làm sạch database thành công!"})
        else:
            return JSONResponse(status_code=500, content={"error": "Làm sạch database thất bại!"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

#  Login API
@app.post("/login")
async def login_api(request: Request):
    data = await request.json()
    email = data.get("mail")
    password = data.get("password")
    token, name, role = await db_login(email, password)
    if token:
        # Lưu thông tin đăng nhập vào session
        request.session["user"] = {"mail": email, "name": name, "role": role}
        return JSONResponse({"message": "Đăng nhập thành công"})
    return JSONResponse(status_code=401, content={"error": "Email hoặc mật khẩu không đúng!"})

#  Logout API
@app.get("/logout")
async def logout_api(request: Request):
    request.session.clear()
    return JSONResponse({"message": "Logged out"})

#########################-user-#####################
# get all users and their details
@app.get("/api/users")
async def api_get_users(request: Request):
    user = request.session.get("user")
    if not user or user.get("role") != 1:
        return JSONResponse(status_code=403, content={"error": "Không có quyền truy cập"})
    users = await get_all_users()
    # users: [(id, mail, name, role, create_at)]
    # Lấy thêm password cho từng user (nếu muốn hiển thị, KHÔNG khuyến khích show password thật)
    result = []
    async with aiosqlite.connect("app/data.db") as db:
        for u in users:
            cursor = await db.execute("SELECT password FROM user WHERE id = ?", (u[0],))
            pwd_row = await cursor.fetchone()
            password = pwd_row[0] if pwd_row else ""
            result.append({
                "id": u[0],
                "mail": u[1],
                "name": u[2],
                "role": u[3],
                "password": password
            })
    return JSONResponse(result)

# change role of user
@app.post("/api/user/role")
async def api_change_role(request: Request):
    user = request.session.get("user")
    if not user or user.get("role") != 1:
        return JSONResponse(status_code=403, content={"error": "Không có quyền truy cập"})
    data = await request.json()
    user_id = int(data.get("id"))
    role = int(data.get("role"))
    await update_user(user_id, role=role)
    await log_activity(request, f"Đổi role user_id={user_id} thành {role}")
    return JSONResponse({"message": "Đã đổi role thành công"})

# Change password of user
@app.post("/api/user/password")
async def api_change_password(request: Request):
    user = request.session.get("user")
    if not user or user.get("role") != 1:
        return JSONResponse(status_code=403, content={"error": "Không có quyền truy cập"})
    data = await request.json()
    user_id = int(data.get("id"))
    password = data.get("password")
    await update_user(user_id, password=password)
    await log_activity(request, f"Đổi mật khẩu user_id={user_id}")
    return JSONResponse({"message": "Đã đổi mật khẩu thành công"})

# delete user
@app.post("/api/user/delete")
async def api_delete_user(request: Request):
    user = request.session.get("user")
    if not user or user.get("role") != 1:
        return JSONResponse(status_code=403, content={"error": "Không có quyền truy cập"})

    data = await request.json()
    try:
        user_id = int(data.get("id"))
    except (TypeError, ValueError):
        return JSONResponse(status_code=400, content={"error": "ID không hợp lệ"})

    # Lấy mail của user cần xoá
    async with aiosqlite.connect("app/data.db") as db:
        cursor = await db.execute("SELECT mail FROM user WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        target_mail = row[0] if row else None

    # Kiểm tra nếu mail trùng với mail của user hiện tại
    if target_mail and target_mail == user.get("mail"):
        return JSONResponse(status_code=400, content={"error": "Không thể tự xoá chính mình"})

    try:
        await delete_user(user_id)
        await log_activity(request, f"Xoá tài khoản user_id={user_id}")
    except ValueError as e:
        return JSONResponse(status_code=404, content={"error": str(e)})

    return JSONResponse({"message": "Đã xoá tài khoản thành công"})

# create new user
@app.post("/api/user/create")
async def api_create_user(request: Request):
    user = request.session.get("user")
    if not user or user.get("role") != 1:
        return JSONResponse(status_code=403, content={"error": "Không có quyền truy cập"})
    data = await request.json()
    mail = data.get("mail")
    name = data.get("name")
    password = data.get("password")
    role = int(data.get("role"))
    ok = await create_user(mail, password, name, role)
    if ok:
        await log_activity(request, f"Tạo tài khoản mới: {mail} ({name}), role={role}")
        return JSONResponse({"message": "Tạo tài khoản thành công"})
    await log_activity(request, f"Tạo tài khoản thất bại: {mail} ({name}), role={role}")
    return JSONResponse(status_code=400, content={"error": "Tài khoản đã tồn tại hoặc lỗi tạo tài khoản"})

#  Get user activities
@app.get("/api/activities")
async def api_get_activities(
    request: Request,
    order: str = "desc",
    limit: str = "10"
):
    user = request.session.get("user")
    if not user:
        return JSONResponse(status_code=401, content={"error": "Chưa đăng nhập"})
    query = "SELECT id, user_id, description, time FROM activity"
    params = []
    if user.get("role") != 1:
        user_id = await get_user_id_by_mail_and_name(user["mail"], user["name"])
        query += " WHERE user_id = ?"
        params.append(user_id)
    query += f" ORDER BY time {'ASC' if order == 'asc' else 'DESC'}"
    if limit != "all":
        try:
            limit_int = int(limit)
            query += " LIMIT ?"
            params.append(limit_int)
        except ValueError:
            query += " LIMIT 10"
            params.append(10)
    async with aiosqlite.connect("app/data.db") as db:
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        result = [{"id": r[0], "user_id": r[1], "description": r[2], "time": r[3]} for r in rows]
        return JSONResponse(result)

#  Get current user information
@app.get("/api/me")
async def api_me(request: Request):
    user = request.session.get("user")
    if not user:
        return JSONResponse(status_code=401, content={"error": "Chưa đăng nhập"})
    return JSONResponse(user)



