import os
import random
import string
from langchain.text_splitter import RecursiveCharacterTextSplitter, CharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain.schema import Document
from app.config import *
from pathlib import Path
import shutil

def generate_id(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# Get the embedding model
def get_embedding_model():
    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        dimensions=EMBEDDING_DIMENSION,
        openai_api_key=OPENAI_API_KEY
    )

# Split text into chunks
def split_text(text, chunk_size=512, chunk_overlap=50):
    splitter = CharacterTextSplitter(
        separator="\n",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len
    )
    return splitter.split_text(text)

# Split documents into chunks
def split_documents(documents, chunk_size=512, chunk_overlap=50):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n"]
    )
    return splitter.split_documents(documents)

# Create or update FAISS database from documents
def create_or_update_faiss_from_documents(documents, embedding_model, vector_db_path):
    # Add ID to documents if not present
    documents_with_id = []
    for doc in documents:
        if 'id' not in doc.metadata:
            doc.metadata['id'] = generate_id()
        documents_with_id.append(doc)

    try:
        # Convert to absolute path and ensure directory exists
        abs_path = os.path.abspath(vector_db_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        if os.path.exists(abs_path):
            print(f"Loading existing DB from {abs_path}")
            db = FAISS.load_local(abs_path, embedding_model, allow_dangerous_deserialization=True)
            print("Adding new documents...")
            db.add_documents(documents_with_id)
        else:
            print(f"Creating new DB at {abs_path}")
            db = FAISS.from_documents(documents_with_id, embedding_model)
        
        print(f"Saving DB to {abs_path}")
        db.save_local(abs_path)
        return db
        
    except Exception as e:
        print(f"Error details: {str(e)}")
        print("Creating new DB from scratch...")
        db = FAISS.from_documents(documents_with_id, embedding_model)
        db.save_local(abs_path)
        return db

# Create or update FAISS database from texts
def create_or_update_faiss_from_texts(texts, embedding_model, vector_db_path):
    documents = []
    for text in texts:
        documents.append(Document(page_content=text, metadata={"id": generate_id()}))

    return create_or_update_faiss_from_documents(documents, embedding_model, vector_db_path)

# Create FAISS database from raw text
def create_db_from_text(raw_text):
    chunks = split_text(raw_text)
    embedding_model = get_embedding_model()
    return create_or_update_faiss_from_texts(chunks, embedding_model, VECTOR_DB_FAISS_PATH)

# Create FAISS database from PDF files in a directory
def create_db_from_files():
    loader = DirectoryLoader(PDF_DATA_PATH, glob="*.pdf", loader_cls=PyPDFLoader)
    documents = loader.load()
    chunks = split_documents(documents)
    embedding_model = get_embedding_model()
    return create_or_update_faiss_from_documents(chunks, embedding_model, VECTOR_DB_FAISS_PATH)

# Ensure vector database exists or create it
def ensure_vector_db_exists():
    """
    Kiểm tra nếu chưa có vector DB (FAISS), thì tạo mới từ text mặc định.
    """
    faiss_index = os.path.join(VECTOR_DB_FAISS_PATH, "index.faiss")
    faiss_pkl = os.path.join(VECTOR_DB_FAISS_PATH, "index.pkl")

    if not os.path.exists(faiss_index) or not os.path.exists(faiss_pkl):
        print("Vector DB chưa tồn tại, tạo mới...")
        create_db_from_text("Thông tin liên hệ. Hotline: 02923 831 015 - 086 2290 808 - 086 2618 369. Website: www.caodangtaydo.edu.vn")

# Perform semantic search with similarity scores
def semantic_search_with_similarity(query, top_k=10):
    """
    Tìm kiếm văn bản tương tự và trả về kết quả dạng text
    """
    try:
        embedding_model = get_embedding_model()
        vectordb = FAISS.load_local(VECTOR_DB_FAISS_PATH, embedding_model, allow_dangerous_deserialization=True)
        results_with_scores = vectordb.similarity_search_with_score(query, k=top_k)

        # Format results as plain text
        output = f"Kết quả tìm kiếm cho: '{query}'\n"
        output += "=" * 50 + "\n\n"
        
        for i, (doc, distance) in enumerate(results_with_scores, 1):
            similarity = 1 / (1 + distance)
            similarity_percent = similarity * 100
            
            output += f"Kết quả #{i}:\n"
            output += f"ID: {doc.metadata.get('id', 'N/A')}\n"
            output += f"Độ tương đồng: {similarity_percent:.2f}%\n"
            output += f"Nội dung: {doc.page_content}\n"
            output += "-" * 50 + "\n\n"

        return output

    except Exception as e:
        return f"Lỗi tìm kiếm: {str(e)}"

# Clean FAISS database and recreate with default contact info
def clean_faiss_database():
    """
    Xóa toàn bộ dữ liệu trong FAISS database
    Returns:
        bool: True nếu xóa thành công, False nếu có lỗi
    """
    try:
        # Convert to Path object
        db_path = Path(VECTOR_DB_FAISS_PATH)
        
        # Kiểm tra và xóa các file trong thư mục
        if db_path.exists():
            print(f"Cleaning FAISS database at {db_path.absolute()}")
            # Xóa toàn bộ thư mục và tạo lại
            shutil.rmtree(db_path)
            db_path.mkdir(parents=True, exist_ok=True)
            print("Database cleaned successfully!")
            create_db_from_text("Thông tin liên hệ. Hotline: 02923 831 015 - 086 2290 808 - 086 2618 369. Website: www.caodangtaydo.edu.vn")
            print("Đã tạo lại database với thông tin liên hệ mặc định.")
            return True
        else:
            print("Database directory doesn't exist. Nothing to clean.")
            return True
            
    except Exception as e:
        print(f"Error cleaning database: {str(e)}")
        return False

# Delete a document by ID and rebuild the database
def delete_document_by_id(doc_id: str) -> tuple[bool, str]:
    """
    Delete a document by rebuilding the database without it
    Args:
        doc_id: ID of document to delete
    Returns:
        tuple[bool, str]: (Success status, Message)
    """
    try:
        # Load existing database
        embedding_model = get_embedding_model()
        db = FAISS.load_local(VECTOR_DB_FAISS_PATH, embedding_model, allow_dangerous_deserialization=True)
        
        # Get all documents
        results = db.similarity_search("", k=1000)  # Increase if you have more documents
        
        # Filter out the document to delete and prepare remaining docs
        remaining_docs = []
        found = False
        
        for doc in results:
            if doc.metadata.get('id') != doc_id:
                remaining_docs.append(Document(
                    page_content=doc.page_content,
                    metadata=doc.metadata
                ))
            else:
                found = True
        
        if not found:
            return False, f"ID không tồn tại trong database: {doc_id}"
        
        # Create new database with remaining documents
        if remaining_docs:
            new_db = FAISS.from_documents(remaining_docs, embedding_model)
            new_db.save_local(VECTOR_DB_FAISS_PATH)
            return True, f"Đã xóa document với ID: {doc_id} và rebuilt database với {len(remaining_docs)} documents"
        else:
            # If no documents left, create empty database
            empty_doc = Document(page_content="", metadata={"id": "initial"})
            new_db = FAISS.from_documents([empty_doc], embedding_model)
            new_db.delete(["initial"])
            new_db.save_local(VECTOR_DB_FAISS_PATH)
            return True, "Đã xóa document cuối cùng và tạo database trống"
            
    except Exception as e:
        return False, f"Lỗi khi rebuild database: {str(e)}"

# Test hàm trong main
if __name__ == "__main__":
    clean_faiss_database()