import os
from datetime import timedelta

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; .env values can also be set as real env vars

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "campusone-dev-secret-change-me")
    DATABASE = os.path.join(BASE_DIR, "database", "campusone.db")
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0").lower() in {"1", "true", "yes"}
    ALLOWED_IMAGE_EXT = {"jpg", "jpeg", "png", "webp"}
    ALLOWED_VIDEO_EXT = {"mp4", "mov", "webm"}
    ALLOWED_DOC_EXT = {"pdf", "jpg", "jpeg", "png", "docx"}

    # Email (optional)
    EMAIL_HOST = os.environ.get("EMAIL_HOST")
    EMAIL_PORT = os.environ.get("EMAIL_PORT")
    EMAIL_USERNAME = os.environ.get("EMAIL_USERNAME")
    EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
    EMAIL_FROM = os.environ.get("EMAIL_FROM")

    # WhatsApp (optional, abstraction only)
    WHATSAPP_API_TOKEN = os.environ.get("WHATSAPP_API_TOKEN")
    WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")

    # AI Assistant (optional)
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    OLLAMA_HOST = os.environ.get("OLLAMA_HOST")  # e.g. http://localhost:11434

    # SLA hours by priority
    SLA_HOURS = {"Urgent": 4, "High": 24, "Normal": 48, "Low": 72}
