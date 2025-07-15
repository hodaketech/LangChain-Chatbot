# Use lightweight Python base image
FROM python:3.11-slim

# Install OS-level dependencies (needed for faiss, pypdf, etc.)
RUN apt-get update && apt-get install -y build-essential libglib2.0-0 libsm6 libxext6 libxrender-dev curl

# Set working directory
WORKDIR /app

# Copy code and requirements
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port for FastAPI
EXPOSE 8000

# Run Gunicorn with Uvicorn workers (production-ready)
CMD ["gunicorn", "app.api:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
