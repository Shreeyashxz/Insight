# ==========================================
# KNOWLEDGE BASE TRAINING LOGIC
# ==========================================
import streamlit as st
import time
import pandas as pd
import io
import json
import hashlib
import os
import fitz  # PyMuPDF for PDF processing
import docx  # For .docx files
from PIL import Image
import pytesseract
from langchain_text_splitters import RecursiveCharacterTextSplitter
import chromadb
from chromadb.utils import embedding_functions

# Import from our project
from config import (
    DB_PATH, EMBEDDING_MODEL_NAME, CHUNK_SIZE, CHUNK_OVERLAP, TESSERACT_CMD
)

# Configure Tesseract path if available
if TESSERACT_CMD and os.path.exists(TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# Module-level singletons to avoid reloading heavy embedding models repeatedly
_CACHED_CLIENT = None
_CACHED_EF = None

def get_chroma_components():
    """Returns singleton ChromaDB PersistentClient and SentenceTransformer embedding function."""
    global _CACHED_CLIENT, _CACHED_EF
    if _CACHED_CLIENT is None:
        _CACHED_CLIENT = chromadb.PersistentClient(path=DB_PATH)
    if _CACHED_EF is None:
        _CACHED_EF = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL_NAME
        )
    return _CACHED_CLIENT, _CACHED_EF

def get_knowledge_base_summary():
    """
    Returns a dictionary summarizing the current knowledge base:
    - total_chunks: int
    - sources: dict of {source_filename: count}
    """
    if not os.path.exists(DB_PATH):
        return {"total_chunks": 0, "sources": {}}
    try:
        client, ef = get_chroma_components()
        collection = client.get_or_create_collection(name="indian_law", embedding_function=ef)
        data = collection.get(include=["metadatas"])
        if not data or not data.get("metadatas"):
            return {"total_chunks": 0, "sources": {}}
        
        sources = {}
        for meta in data["metadatas"]:
            src = meta.get("source", "Unknown")
            sources[src] = sources.get(src, 0) + 1
        return {"total_chunks": len(data["metadatas"]), "sources": sources}
    except Exception:
        return {"total_chunks": 0, "sources": {}}

def delete_source_from_db(source_name):
    """Deletes all chunks belonging to a specific source document."""
    try:
        client, ef = get_chroma_components()
        collection = client.get_or_create_collection(name="indian_law", embedding_function=ef)
        collection.delete(where={"source": source_name})
        return True, f"Successfully removed '{source_name}' from knowledge base."
    except Exception as e:
        return False, f"Failed to delete '{source_name}': {str(e)}"

def clear_entire_db():
    """Deletes the entire collection to allow a fresh start."""
    try:
        client, _ = get_chroma_components()
        client.delete_collection(name="indian_law")
        return True, "Knowledge base reset successfully."
    except Exception as e:
        return False, f"Failed to reset knowledge base: {str(e)}"

def detect_best_text_column(df):
    """Intelligently detects which column in a DataFrame contains the main document text."""
    preferred_names = {"text", "content", "document", "clause", "law", "body", "section", "article", "description"}
    col_lower = {col.lower(): col for col in df.columns}
    
    for preferred in preferred_names:
        if preferred in col_lower:
            return col_lower[preferred]
            
    # Fallback: Pick the column with the highest average string length
    max_avg_len = -1
    best_col = df.columns[0]
    for col in df.columns:
        try:
            avg_len = df[col].astype(str).str.len().mean()
            if avg_len > max_avg_len:
                max_avg_len = avg_len
                best_col = col
        except Exception:
            continue
    return best_col

def train_knowledge_base(uploaded_files, comment="", debug=False, debug_placeholder=None):
    """
    Processes uploaded documents, splits them into chunks, generates embeddings,
    and stores/upserts them into ChromaDB with deterministic IDs to prevent duplicates.
    """
    status_container = st.status("🚀 Starting Training Process...", expanded=True)
    log_messages = []

    def log_message(message):
        status_container.write(message)
        if debug and debug_placeholder:
            timestamp = time.strftime('%H:%M:%S')
            log_messages.append(f"[{timestamp}] {message}")
            debug_placeholder.code("\n".join(log_messages), language="log")

    try:
        log_message("📂 Reading and processing files...")
        all_chunks = []
        all_metadatas = []
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", " ", ""]
        )

        num_files = len(uploaded_files)
        progress_bar = status_container.progress(0, text=f"Processing 0 of {num_files} files...")

        for i, uploaded_file in enumerate(uploaded_files):
            progress_bar.progress((i + 1) / num_files, text=f"Processing file {i+1}/{num_files}: {uploaded_file.name}")

            try:
                file_bytes = uploaded_file.read()
                file_name_lower = uploaded_file.name.lower()
                text_based_content = ""

                # --- 1. Structured Data (CSV) ---
                if file_name_lower.endswith(".csv"):
                    file_content = file_bytes.decode("utf-8-sig")
                    df = pd.read_csv(io.StringIO(file_content))
                    if not df.empty and len(df.columns) > 0:
                        doc_col = detect_best_text_column(df)
                        meta_cols = [c for c in df.columns if c != doc_col]
                        for _, row in df.iterrows():
                            doc_text = str(row[doc_col]).strip()
                            if doc_text and doc_text.lower() != "nan":
                                all_chunks.append(doc_text)
                                new_meta = {"source": uploaded_file.name}
                                if comment:
                                    new_meta["comment"] = comment
                                for col in meta_cols:
                                    new_meta[str(col).lower()[:60]] = str(row[col])[:200]
                                all_metadatas.append(new_meta)
                        log_message(f"✅ Processed {len(df)} rows from CSV: {uploaded_file.name} (using column '{doc_col}')")
                    continue

                # --- 2. Structured Data (JSON / JSONL) ---
                elif file_name_lower.endswith(".jsonl"):
                    file_content = file_bytes.decode("utf-8-sig").strip()
                    rows_processed = 0

                    def process_json_object(data):
                        nonlocal rows_processed
                        if not isinstance(data, dict) or not data:
                            return
                        keys = list(data.keys())
                        preferred_keys = ["text", "content", "document", "clause", "law", "body", "section"]
                        doc_key = None
                        for pk in preferred_keys:
                            for k in keys:
                                if pk == k.lower():
                                    doc_key = k
                                    break
                            if doc_key:
                                break
                        if not doc_key:
                            doc_key = keys[0]

                        doc_text = str(data[doc_key]).strip()
                        if doc_text and doc_text.lower() != "nan":
                            all_chunks.append(doc_text)
                            new_meta = {"source": uploaded_file.name}
                            if comment:
                                new_meta["comment"] = comment
                            for key in keys:
                                if key != doc_key:
                                    new_meta[str(key).lower()[:60]] = str(data[key])[:200]
                            all_metadatas.append(new_meta)
                            rows_processed += 1

                    try:
                        data = json.loads(file_content)
                        if isinstance(data, list):
                            for item in data:
                                process_json_object(item)
                        elif isinstance(data, dict):
                            process_json_object(data)
                    except json.JSONDecodeError:
                        for line in file_content.splitlines():
                            if not line.strip():
                                continue
                            try:
                                process_json_object(json.loads(line))
                            except json.JSONDecodeError:
                                pass

                    if rows_processed > 0:
                        log_message(f"✅ Processed {rows_processed} records from: {uploaded_file.name}")
                    continue

                # --- 3. Unstructured Documents (PDF) ---
                elif file_name_lower.endswith(".pdf"):
                    doc = fitz.open(stream=file_bytes, filetype="pdf")
                    for page_num, page in enumerate(doc):
                        page_text = page.get_text()
                        # If page text is minimal (e.g. scanned page), use PyMuPDF built-in rasterizer + OCR
                        if len(page_text.strip()) < 40:
                            try:
                                pix = page.get_pixmap(dpi=150)
                                img = Image.open(io.BytesIO(pix.tobytes("png")))
                                ocr_text = pytesseract.image_to_string(img)
                                if ocr_text.strip():
                                    page_text = ocr_text
                            except Exception:
                                pass
                        text_based_content += page_text + "\n"

                # --- 4. Unstructured Documents (DOCX) ---
                elif file_name_lower.endswith(".docx"):
                    doc = docx.Document(io.BytesIO(file_bytes))
                    text_based_content = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])

                # --- 5. Plain Text / Markdown ---
                elif file_name_lower.endswith((".txt", ".md")):
                    text_based_content = file_bytes.decode("utf-8-sig")

                # --- 6. Plain JSON ---
                elif file_name_lower.endswith(".json"):
                    file_content = file_bytes.decode("utf-8-sig")
                    data = json.loads(file_content)
                    text_based_content = json.dumps(data, indent=2)

                # --- 7. Images with OCR (PNG, JPG, BMP, TIFF) ---
                elif file_name_lower.endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff")):
                    try:
                        img = Image.open(io.BytesIO(file_bytes))
                        text_based_content = pytesseract.image_to_string(img)
                        if not text_based_content.strip():
                            log_message(f"⚠️ No readable text detected in image: {uploaded_file.name}")
                    except Exception as ocr_err:
                        log_message(f"⚠️ OCR failed on {uploaded_file.name}: {ocr_err}")

                # Split extracted unstructured text into chunks
                if text_based_content.strip():
                    chunks = text_splitter.split_text(text_based_content)
                    all_chunks.extend(chunks)
                    chunk_metadata = {"source": uploaded_file.name}
                    if comment:
                        chunk_metadata["comment"] = comment
                    all_metadatas.extend([chunk_metadata for _ in range(len(chunks))])
                    log_message(f"✅ Extracted {len(chunks)} chunks from: {uploaded_file.name}")

            except Exception as e:
                log_message(f"⚠️ Error reading {uploaded_file.name}: {e}")
                continue
        
        progress_bar.empty()

        if not all_chunks:
            status_container.update(label="No readable text found in uploaded files!", state="error")
            return

        log_message("🧠 Connecting to Vector Database...")
        client, ef = get_chroma_components()
        collection = client.get_or_create_collection(
            name="indian_law",
            embedding_function=ef
        )
        
        # Generate deterministic IDs based on source and chunk content to prevent duplication
        ids = []
        for idx, (chunk, meta) in enumerate(zip(all_chunks, all_metadatas)):
            src = meta.get("source", "doc")
            chunk_hash = hashlib.sha256(f"{src}_{idx}_{chunk[:80]}".encode("utf-8")).hexdigest()[:24]
            ids.append(f"doc_{chunk_hash}")
        
        # Batch upsert to vector store
        batch_size = 256
        num_batches = (len(all_chunks) + batch_size - 1) // batch_size
        for i in range(0, len(all_chunks), batch_size):
            batch_documents = all_chunks[i:i+batch_size]
            batch_metadatas = all_metadatas[i:i+batch_size]
            batch_ids = ids[i:i+batch_size]
            
            # Use upsert to cleanly update or add chunks without duplication
            collection.upsert(
                documents=batch_documents,
                metadatas=batch_metadatas,
                ids=batch_ids
            )
            log_message(f"💾 Upserted batch {i//batch_size + 1} of {num_batches} to vector store...")

        status_container.update(label="🎉 Knowledge Base Updated Successfully!", state="complete", expanded=False)
        st.success(f"Successfully indexed {len(all_chunks)} knowledge chunks into the legal database.")
        time.sleep(1.5)
        
    except Exception as e:
        if "Embedding function conflict" in str(e):
            status_container.update(label="Database Conflict!", state="error")
            st.error("Embedding model conflict: The database was created with a different embedding model.")
            st.warning("Click 'Clear Entire Knowledge Base' in the Training tab to reset the store.")
        else:
            status_container.update(label="Training Failed", state="error")
            st.error(f"Error during training: {e}")
            if debug and debug_placeholder:
                import traceback
                log_messages.append(traceback.format_exc())
                debug_placeholder.code("\n".join(log_messages), language="log")
