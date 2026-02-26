import os
from dotenv import load_dotenv

load_dotenv(override=True)  # Load environment variables from .env file, allowing override with actual env vars

class Config:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")