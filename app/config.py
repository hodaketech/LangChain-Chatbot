import os

# OpenAI Config - text-embedding-3-small
OPENAI_API_KEY = ""
# Google Config - Gemini
GOOGLE_API_KEY = ""
# Path Config
PDF_DATA_PATH = "app/data"
VECTOR_DB_PATH = os.path.join(os.path.dirname(__file__), "vectorstores")
VECTOR_DB_FAISS_PATH = os.path.join(VECTOR_DB_PATH, "db_faiss")
# Model Config
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = "1536"
LLM_MODEL = "gemini-2.0-flash"
# Chain Config
CHUNK_SIZE = "512"
CHUNK_OVERLAP = "50"
RETRIEVER_K = "3"
#template
TEMPLATE = """
    Bạn là chatbot RAG, hãy Sử dụng các ngữ cảnh sau đây để trả lời câu hỏi một cách chính xác và ngắn gọn. Nếu trong ngữ cảnh không có thông tin cho câu trả lời, hãy nói "Câu hỏi này nằm ngoài tập dữ liệu của tôi", sau đó tự trả lời theo kiến thức tự có.
    -------------------
    Ngữ cảnh: {context}
    -------------------
    Câu hỏi: {question}
    """
#top k
TOP_K = 3
#Admin account default
ADMIN_EMAIL = "admin@a.com"
ADMIN_PASSWORD = "123456"
ADMIN_NAME = "Admin"
