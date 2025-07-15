import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from app.config import *
from app.prepare_vector_db import ensure_vector_db_exists

# Ensure environment variables are set
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# Load the LLM model
def load_llm():
    return ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        temperature=0.0,
    )

# Create a prompt template for the question-answering chain
def create_prompt(template):
    return PromptTemplate(template=template, input_variables=["context", "question"])

# Create a question-answering chain using the LLM and FAISS vector store
def create_qa_chain(prompt, llm, db):
    return RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=db.as_retriever(search_kwargs={"k": TOP_K}),
        chain_type_kwargs={"prompt": prompt},
        return_source_documents=True
    )

# Read the FAISS vector database
def read_vectors_db():
    # Đảm bảo vector DB tồn tại
    ensure_vector_db_exists()

    embedding_model = OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        dimensions=EMBEDDING_DIMENSION,
        openai_api_key=OPENAI_API_KEY
    )
    return FAISS.load_local(
        VECTOR_DB_FAISS_PATH,
        embedding_model,
        allow_dangerous_deserialization=True  # Cho phép pickle nếu bạn tin tưởng
    )

if __name__ == "__main__":
    # test the question-answering chain
    db = read_vectors_db()
    llm = load_llm()
    prompt = create_prompt(TEMPLATE)
    qa_chain = create_qa_chain(prompt, llm, db)

    print("Nhập câu hỏi (gõ 'exit' để thoát):")
    while True:
        question = input(">>> ").strip()
        if question.lower() == "exit":
            print("Thoát chương trình.")
            break

        response = qa_chain.invoke({"query": question})
        print("\nKết quả trả lời:\n", response['result'])
        print("\nNguồn tham chiếu:")
        for doc in response['source_documents']:
            print("-", doc.page_content.strip())
        print("\n---")

