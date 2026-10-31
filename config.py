# ==========================================
# CONFIGURATION & CONSTANTS
# ==========================================
import os

# 1. LLM Configuration (for OpenAI-compatible API served via LM Studio / Ollama / vLLM)
LLM_API_BASE = os.getenv("LLM_API_BASE", "http://localhost:1234/v1")  # Base URL of LLM API
LLM_API_KEY = os.getenv("LLM_API_KEY", "lm-studio")                  # API key
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "local-model")          # Default model name
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "300"))                   # Request timeout in seconds

# 2. [WINDOWS-SPECIFIC] OCR Paths (Tesseract & Poppler)
DEFAULT_TESSERACT_PATHS = [
    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
    r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
    os.path.expanduser(r'~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe')
]
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "")
if not TESSERACT_CMD:
    for path in DEFAULT_TESSERACT_PATHS:
        if os.path.exists(path):
            TESSERACT_CMD = path
            break
if not TESSERACT_CMD:
    TESSERACT_CMD = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# 3. Database Location
DB_PATH = os.getenv("DB_PATH", "./legal_db")

# 4. Analysis Character Limit
# Maximum characters of contract to send in a single LLM context window
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "14000"))

# 5. RAG Configuration
RAG_ANALYSIS_RESULTS = 3  # Number of relevant chunks per query for contract analysis
RAG_CHAT_RESULTS = 3      # Default relevant chunks for chat tab

# 6. Embedding & Chunking Configuration
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"  # Fast and reliable sentence-transformer
CHUNK_SIZE = 1000                           # Target size of each text chunk in characters
CHUNK_OVERLAP = 200                         # Characters overlap between consecutive chunks

# 7. Targeted RAG Legal Risk Topics
# Used for targeted clause-to-law retrieval instead of naive random chunk sampling
LEGAL_RISK_TOPICS = [
    "indemnity liability unlimited hold harmless damages section 73 74",
    "non-compete restraint of trade post-termination non-solicitation section 27",
    "intellectual property copyright assignment moral rights work for hire creator portfolio",
    "termination for convenience immediate notice period severance cure period",
    "payment terms net 15 30 delay penalty interest withholding deduction",
    "dispute resolution jurisdiction arbitration seated freelancer home court",
    "confidentiality non-disclosure perpetuity broad definition trade secrets"
]

# 8. The "Fairness" Baseline
FAIR_STANDARD_FILE = "fair_standard.txt"
DEFAULT_FAIR_STANDARD = """STANDARD FAIR TERMS (INDIAN FREELANCE UNION BENCHMARK):
1. Payment Terms: Net 15 or Net 30 days maximum.
2. Intellectual Property: IP transfers to client ONLY upon full payment. Creator retains portfolio rights.
3. Termination: Mutual notice period (e.g., 15-30 days). No immediate termination without cause.
4. Non-Compete: strictly limited to direct competitors during the project term only. Post-term non-competes are void under Section 27.
5. Indemnity: Capped at the total contract value. No unlimited liability.
6. Dispute Resolution: Arbitration in the freelancer's home city (India).
"""
