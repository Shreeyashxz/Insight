# ==========================================
# INSIGHT - AI LEGAL SENTINEL
#
# Main application entry point. This file initializes the Streamlit
# interface and coordinates the different modules of the application.
# ==========================================

import os
import streamlit as st
import pytesseract

# Import from our project modules
from ui import render_sidebar, render_analyzer_tab, render_training_tab, render_chat_tab
from config import TESSERACT_CMD

# Configure Website Title and Layout
st.set_page_config(page_title="Insight - AI Legal Sentinel", page_icon="⚖️", layout="wide")

# Automatic Windows Tesseract Configuration
if TESSERACT_CMD and os.path.exists(TESSERACT_CMD):
    try:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    except Exception:
        pass

def main():
    """Main function to run the Streamlit application."""
    selected_model, debug_mode = render_sidebar()

    # Create the main tabs for the application features
    tab1, tab2, tab3 = st.tabs(["🕵️ Analyze Contract", "📚 Train Knowledge Base", "💬 Chat with AI"])

    with tab1:
        render_analyzer_tab(selected_model, debug_mode)

    with tab2:
        render_training_tab()

    with tab3:
        render_chat_tab(selected_model)

if __name__ == "__main__":
    main()

# ==========================================
#               CHANGELOG
# ==========================================
# v2.2 (Hardened & Optimized)
# - Targeted RAG: Clause and legal topic retrieval replaces naive 5-chunk sampling.
# - PyMuPDF native rendering: Scanned PDF OCR works without external Poppler dependencies.
# - Image OCR in Training: Full support for png, jpg, jpeg, bmp, and tiff knowledge indexing.
# - Duplicate Prevention: Deterministic chunk hashing with collection.upsert().
# - Knowledge Base Management: View indexed document sources, count chunks, and delete per source.
# - Prompt Injection Hardening: XML isolation and strict system boundary instructions.
# - Resilient JSON Output: Structured schema mode with json_repair fallback.
# - Performance Caching: Singleton ChromaDB client and embedding model reuse.
# - Safe Session Reset: Fixed StreamlitAPIException on uploader state reset.
# ==========================================
