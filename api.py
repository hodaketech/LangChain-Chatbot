from fastapi import FastAPI, Form, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel
import os
import shutil
from datetime import datetime
import config
from qabot import read_vectors_db, load_llm, create_prompt, create_qa_chain
from prepare_vector_db import create_db_from_text, create_db_from_files, delete_document_by_id
from config import TEMPLATE, PDF_DATA_PATH
from prepare_vector_db import semantic_search_with_similarity
import json

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Đảm bảo thư mục data tồn tại
if not os.path.exists(PDF_DATA_PATH):
    os.makedirs(PDF_DATA_PATH)

# Root route trả về index.html
@app.get("/")
async def read_root():
    return FileResponse('static/home.html')

# Chuẩn bị các components cho chatbot
db = read_vectors_db()
llm = load_llm()
prompt = create_prompt(TEMPLATE)
qa_chain = create_qa_chain(prompt, llm, db)

class QuestionRequest(BaseModel):
    question: str

@app.post("/ask")
async def ask_question(req: QuestionRequest):
    result = qa_chain.invoke({"query": req.question})
    return {
        "answer": result["result"],
        "sources": [doc.page_content.strip() for doc in result["source_documents"]]
    }

# Routes xử lý upload và process data
@app.post("/process-text")
async def process_text(text: str = Form(...)):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        text_filename = f"{PDF_DATA_PATH}/text_{timestamp}.txt"
        
        with open(text_filename, "w", encoding="utf-8") as f:
            f.write(text)

        create_db_from_text(text)
        return JSONResponse(
            status_code=200,
            content={"message": "Xử lý văn bản thành công"}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Lỗi khi xử lý văn bản: {str(e)}"}
        )

@app.post("/process-pdf")
async def process_pdf(pdf: UploadFile = File(...)):
    try:
        pdf_path = f"{PDF_DATA_PATH}/{pdf.filename}"
        with open(pdf_path, "wb") as f:
            shutil.copyfileobj(pdf.file, f)
        
        create_db_from_files()
        return JSONResponse(
            status_code=200,
            content={"message": "Xử lý PDF thành công"}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Lỗi khi xử lý PDF: {str(e)}"}
        )

# Endpoint semantic search
class QuestionRequest(BaseModel):
    question: str

@app.post("/semantic-search")
async def semantic_search(req: QuestionRequest):
    output = semantic_search_with_similarity(req.question, top_k=10)
    return {"result": output}

# Delete document endpoint
@app.post("/delete-document")
async def delete_document(request: dict):
    try:
        doc_id = request.get('doc_id')
        if not doc_id:
            return Response(
                content="Missing document ID",
                media_type="text/plain",
                status_code=400
            )
            
        success, message = delete_document_by_id(doc_id)
        
        return Response(
            content=message,
            media_type="text/plain",
            status_code=200 if success else 400
        )
        
    except Exception as e:
        return Response(
            content=f"Error: {str(e)}",
            media_type="text/plain",
            status_code=500
        )

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

@app.post("/update-config")
async def update_config(settings: dict):
    try:
        # Update config.py file
        config_path = os.path.join(os.path.dirname(__file__), 'config.py')
        with open(config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Update values
        updated_lines = []
        for line in lines:
            for key, value in settings.items():
                if line.startswith(key + " ="):
                    if isinstance(value, str):
                        line = f'{key} = "{value}"\n'
                    else:
                        line = f'{key} = {value}\n'
            updated_lines.append(line)
        
        # Write back to file
        with open(config_path, 'w', encoding='utf-8') as f:
            f.writelines(updated_lines)
            
        return JSONResponse(content={"message": "Settings updated successfully"})
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

