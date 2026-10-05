import os
from dotenv import load_dotenv

load_dotenv()

PORT = int(os.getenv("PORT", "8000"))
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5:1.5b")
AI_API_SECRET = os.getenv("AI_API_SECRET", "miclub_secreto_super_seguro_2026")
