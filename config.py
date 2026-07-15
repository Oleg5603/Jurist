import os

from dotenv import load_dotenv

load_dotenv()

APP_LOGIN = os.getenv("APP_LOGIN", "")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CHATS_DIR = os.path.join(DATA_DIR, "chats")
DOCUMENTS_DIR = os.path.join(DATA_DIR, "documents")
CONTRACTS_DIR = os.path.join(DATA_DIR, "contracts")
CASES_DIR = os.path.join(DATA_DIR, "cases")
