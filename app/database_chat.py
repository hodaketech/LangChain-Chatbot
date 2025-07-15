import aiosqlite
from datetime import datetime
import os

# Define the path for the chat database
CHAT_DB_PATH = os.path.join(os.path.dirname(__file__), "chat.db")

# Initialize the chat database and create the chat_history table if it doesn't exist
async def init_chat_db():
    async with aiosqlite.connect(CHAT_DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT,
                answer TEXT,
                sources TEXT,
                time TEXT
            );
        """)
        await db.commit()

# Call this function at the start of your application to ensure the database is ready
async def save_chat(question: str, answer: str, sources: str):
    async with aiosqlite.connect(CHAT_DB_PATH) as db:
        await db.execute(
            "INSERT INTO chat_history (question, answer, sources, time) VALUES (?, ?, ?, ?)",
            (question, answer, sources, datetime.now().isoformat())
        )
        await db.commit()

# Function to retrieve chat history with optional filters
async def get_chat_history(order: str = "desc", limit: int = 10, start_date: str = None, end_date: str = None):
    query = "SELECT question, answer, sources, time FROM chat_history"
    params = []
    where = []
    if start_date:
        where.append("time >= ?")
        params.append(start_date)
    if end_date:
        where.append("time <= ?")
        params.append(end_date)
    if where:
        query += " WHERE " + " AND ".join(where)
    query += f" ORDER BY time {'ASC' if order == 'asc' else 'DESC'} LIMIT ?"
    params.append(limit)
    async with aiosqlite.connect(CHAT_DB_PATH) as db:
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [{"question": r[0], "answer": r[1], "sources": r[2], "time": r[3]} for r in rows]