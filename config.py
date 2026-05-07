# config.py
# --- Google service account ---
SERVICE_ACCOUNT_FILE = "credentials/service_account.json"

# --- Google Drive folder ---
DRIVE_FOLDER_ID = "12K6TByD5Jbm3hpXSVxE_JYt22mhLH5W2"

# --- Models ---
AVAILABLE_MODELS = ["llama3.1:8b", "mistral:7b"]
DEFAULT_MODEL = "llama3.1:8b"
EMBEDDING_MODEL = "nomic-embed-text"
OLLAMA_BASE_URL = "http://localhost:11434"

# --- Text Splitting ---
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

# --- Retrieval ---
TOP_K_RESULTS = 3

# --- Memory ---
MAX_HISTORY_TURNS = 5  # each turn = 1 user message + 1 assistant reply