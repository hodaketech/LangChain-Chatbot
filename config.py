import os

# OpenAI Config
OPENAI_API_KEY = ""
# Google Config
GOOGLE_API_KEY = ""
# Path Config
PDF_DATA_PATH = "data"
VECTOR_DB_PATH = os.path.join(os.path.dirname(__file__), "vectorstores")
VECTOR_DB_FAISS_PATH = os.path.join(VECTOR_DB_PATH, "db_faiss")
# Model Config
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
LLM_MODEL = "gemini-1.5-flash"
# Chain Config
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50
RETRIEVER_K = 3
#template
TEMPLATE = """
    Sử dụng thông tin sau đây để trả lời câu hỏi một cách chính xác và ngắn gọn. Nếu không biết câu trả lời, hãy nói "Câu hỏi này nằm ngoài tập dữ liệu của tôi", sau đó tự trả lời theo kiến thức tự có.
    -------------------
    {context}
    -------------------
    Câu hỏi: {question}
    Trả lời:
    """
#top k
TOP_K = 3
