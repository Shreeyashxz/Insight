# ==========================================
# USER INTERFACE (Frontend)
# ==========================================
import streamlit as st
import json
import re
import openai
import plotly.graph_objects as go
import json_repair

# Import from our project
from analyzer import ContractAnalyzer
from training import (
    train_knowledge_base,
    get_knowledge_base_summary,
    delete_source_from_db,
    clear_entire_db
)
from config import (
    LLM_API_BASE,
    LLM_API_KEY,
    LLM_MODEL_NAME,
    LLM_TIMEOUT,
    RAG_CHAT_RESULTS,
    MAX_CONTEXT_CHARS
)

def render_sidebar():
    """Renders the sidebar UI and returns the selected model and debug mode."""
    with st.sidebar:
        st.title("Insight Sentinel 🇮🇳")
        st.markdown("### *AI Legal Sentinel*")
        st.caption("v2.2 | Production Ready")
        st.markdown("---")
        
        selected_model = None
        try:
            client = openai.OpenAI(
                base_url=LLM_API_BASE,
                api_key=LLM_API_KEY,
                timeout=10.0,
            )
            models_info = client.models.list()
            models = [m.id for m in models_info.data]

            if models:
                st.success(f"✅ Found {len(models)} Model(s)")
                def_idx = 0
                try:
                    def_idx = models.index(LLM_MODEL_NAME)
                except ValueError:
                    try:
                        def_idx = next(i for i, model_name in enumerate(models) if any(m in model_name.lower() for m in ["llama", "qwen", "mistral"]))
                    except StopIteration:
                        def_idx = 0

                selected_model = st.selectbox("Select AI Model", models, index=def_idx)
                st.caption(f"Active Model: **{selected_model}**")
            else:
                st.error("⚠️ No models found at the API endpoint!")
                st.info(f"Ensure your LLM server (LM Studio / Ollama) is running at `{LLM_API_BASE}`.")

        except openai.APIConnectionError:
            st.error("❌ LLM server is not running!")
            st.caption(f"Make sure your local server is running at `{LLM_API_BASE}`.")
        except Exception as e:
            st.error("Could not retrieve models.")
            st.caption(f"Error: {e}")
        
        st.markdown("---")
        debug_mode = st.checkbox("⚙️ Debug Mode", value=False, help="Show technical diagnostics and verbose outputs.")
        
        return selected_model, debug_mode

def render_analyzer_tab(selected_model, debug_mode):
    """Renders the 'Analyze Contract' tab."""
    st.markdown("#### *Check your contract for risks & legal pitfalls*")
    
    # Initialize file uploader key in session state to safely reset without StreamlitAPIException
    if "upload_key" not in st.session_state:
        st.session_state.upload_key = 0
    if "analyzer_messages" not in st.session_state:
        st.session_state.analyzer_messages = []

    uploaded_contract = st.file_uploader(
        "Upload Contract (PDF, DOCX, Text, or Image)",
        type=["pdf", "docx", "txt", "png", "jpg", "jpeg", "bmp", "tiff"],
        key=f"contract_upload_{st.session_state.upload_key}"
    )

    if uploaded_contract:
        if uploaded_contract.file_id != st.session_state.get('analyzed_contract_id'):
            st.session_state.analyzer_messages = []
            st.session_state.analyzed_contract_id = uploaded_contract.file_id

        if not selected_model:
            st.warning("Please select an AI model from the sidebar to begin analysis.")
            st.stop()

        analyzer = ContractAnalyzer(model_name=selected_model)
        
        with st.status("Analyzing Contract...", expanded=True) as status:
            status.write("📂 Reading document content...")
            file_bytes = uploaded_contract.read()
            file_name_lower = uploaded_contract.name.lower()
            text = ""
            
            if file_name_lower.endswith(".pdf"):
                text = analyzer.extract_text_from_pdf(file_bytes)
            elif file_name_lower.endswith(".docx"):
                text = analyzer.extract_text_from_docx(file_bytes)
            elif file_name_lower.endswith(".txt"):
                text = file_bytes.decode("utf-8-sig", errors="ignore")
            elif file_name_lower.endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff")):
                text = analyzer.extract_text_from_image(file_bytes)
            else:
                st.error(f"Unsupported file format: {uploaded_contract.name}")
                st.stop()
            
            if not text.strip():
                st.error("Unable to extract text from document. If it is an image/scanned PDF, verify Tesseract OCR is installed.")
                status.update(label="Analysis failed: Empty document", state="error")
                st.stop()
                
            status.write(f"✅ Extracted {len(text):,} characters.")
            status.write("🔍 Consulting legal vector knowledge base for relevant statutes & standards...")
            status.write("🤖 Performing AI risk assessment...")
            
            json_str = analyzer.analyze_contract(text)
            
            if '"error":' in json_str.lower():
                try:
                    error_detail = json.loads(json_str).get('error', 'Unknown error.')
                    st.error(f"Analysis failed: {error_detail}")
                except Exception:
                    st.error(f"Analysis failed: {json_str}")
                status.update(label="Analysis failed", state="error")
                st.stop()
            
            status.update(label="Analysis Complete!", state="complete", expanded=False)

        # Parse AI output safely
        data = None
        try:
            match = re.search(r'\{.*\}', json_str, re.DOTALL)
            data_str = match.group(0) if match else json_str
            data = json.loads(data_str)
        except Exception:
            try:
                data = json_repair.loads(json_str)
            except Exception as parse_err:
                st.error(f"Error parsing AI response: {parse_err}")
                st.code(json_str)
                st.stop()

        # Check for context truncation notification
        if data.get("is_truncated"):
            st.warning(f"⚠️ **Long Document Notice:** Contract contains {data.get('original_char_count'):,} characters. To stay within the model's optimal context window, the first {MAX_CONTEXT_CHARS:,} characters were analyzed.")

        st.subheader("📊 Contract Analysis Results")
        col1, col2, col3 = st.columns([2, 1, 3])
        
        with col1:
            score = int(data.get('risk_score', 0))
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=score,
                title={'text': "Risk Score", 'font': {'size': 20}},
                gauge={
                    'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "gray"},
                    'bar': {'color': "black", 'thickness': 0.25},
                    'bgcolor': "rgba(0,0,0,0)",
                    'borderwidth': 0,
                    'steps': [
                        {'range': [0, 30], 'color': '#28a745'},
                        {'range': [30, 70], 'color': '#ffc107'},
                        {'range': [70, 100], 'color': '#dc3545'}
                    ],
                }
            ))
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                height=200, 
                margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        with col2:
            verdict = data.get('verdict', 'N/A')
            st.metric(label="Overall Verdict", value=verdict)

        with col3:
            st.info(f"**Executive Summary:**\n\n{data.get('summary', 'No summary available.')}")

        st.subheader("🗣️ ELI5 Takeaways (Plain English)")
        takeaways = data.get('eli5_takeaways', [])
        if takeaways:
            for point in takeaways:
                st.success(f"• {point}")
        else:
            st.write("No simple takeaways were generated.")

        st.subheader("🚩 Red Flags & Unfair Clauses")
        red_flags = data.get('red_flags', [])
        if red_flags:
            for item in red_flags:
                verdict_str = item.get('verdict', 'Warning')
                color = "red" if "High" in verdict_str else ("orange" if "Medium" in verdict_str else "blue")
                clause_title = item.get('clause', 'Clause')[:120]
                
                with st.expander(f"⚠️ {clause_title}..."):
                    st.markdown(f"**Severity:** :{color}[{verdict_str}]")
                    st.markdown(f"**Identified Issue:** {item.get('issue', 'N/A')}")
                    st.markdown(f"**Suggested Fix / Amendment:** {item.get('fix', 'N/A')}")
        else:
            st.write("No severe red flags were detected.")

        st.markdown("---")
        with st.expander("💬 Advise Section (Ask questions about this contract)", expanded=False):
            for message in st.session_state.analyzer_messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            if prompt := st.chat_input("Ask a question about this contract...", key="analyzer_chat_input"):
                st.session_state.analyzer_messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)
                
                with st.chat_message("assistant"):
                    with st.spinner("Analyzing contract clause..."):
                        chat_response = analyzer.chat_with_contract(text, prompt, st.session_state.analyzer_messages)
                        st.markdown(chat_response)
                        st.session_state.analyzer_messages.append({"role": "assistant", "content": chat_response})

        st.markdown("---")
        if st.button("🔄 Analyze Another Contract", key="analyze_another_contract"):
            st.session_state.analyzed_contract_id = None
            st.session_state.analyzer_messages = []
            st.session_state.upload_key += 1
            st.rerun()

def render_training_tab():
    """Renders the 'Train Knowledge Base' tab with document management capabilities."""
    st.markdown("#### *Knowledge Base Management*")
    st.info("Upload legal documents (Acts, Rules, Court Rulings, Benchmark Standards) to expand the AI's legal knowledge.")
    
    col_up, col_info = st.columns([3, 2])
    
    with col_up:
        train_files = st.file_uploader(
            "Select Legal Reference Documents (PDF, DOCX, TXT, CSV, JSON, JSONL, Images)",
            type=["pdf", "docx", "txt", "md", "csv", "json", "jsonl", "png", "jpg", "jpeg", "bmp", "tiff"],
            accept_multiple_files=True,
            key="train_upload"
        )
        training_comment = st.text_input(
            "Training Tag / Reference Note (Optional)",
            placeholder="e.g. 'Indian Contract Act 1872', 'Arbitration & Conciliation Act'",
            key="training_comment"
        )
        
        debug_mode = st.checkbox("Show Advanced Training Logs", key="train_debug")
        debug_placeholder = st.empty()

        if train_files:
            if st.button("🧠 Train Knowledge Base", type="primary"):
                train_knowledge_base(train_files, comment=training_comment, debug=debug_mode, debug_placeholder=debug_placeholder)
                st.rerun()

    with col_info:
        st.markdown("##### 📚 Current Knowledge Base")
        summary = get_knowledge_base_summary()
        st.metric("Total Legal Chunks Indexed", summary["total_chunks"])
        
        if summary["sources"]:
            st.markdown("**Indexed Documents:**")
            for source_name, count in summary["sources"].items():
                c_name, c_del = st.columns([3, 1])
                c_name.caption(f"📄 **{source_name}** ({count} chunks)")
                if c_del.button("🗑️", key=f"del_{source_name}", help=f"Remove {source_name}"):
                    success, msg = delete_source_from_db(source_name)
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
                    st.rerun()
            
            st.markdown("---")
            if st.button("⚠️ Clear Entire Knowledge Base", key="clear_kb_btn"):
                success, msg = clear_entire_db()
                if success:
                    st.success(msg)
                else:
                    st.error(msg)
                st.rerun()
        else:
            st.caption("No documents in knowledge base yet. Upload references to get started.")

def render_chat_tab(selected_model):
    """Renders the 'Chat with AI' tab with streaming RAG Q&A."""
    st.markdown("#### *Direct Consultation with AI Legal Sentinel*")
    st.caption("Ask questions about Indian law, contract fairness, and your uploaded reference documents.")

    rag_limit = st.slider(
        "Knowledge Depth (Retrieved Legal Chunks)", 
        min_value=1, 
        max_value=8, 
        value=RAG_CHAT_RESULTS,
        help="Controls how many relevant chunks from your knowledge base are provided to the AI."
    )

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "generating" not in st.session_state:
        st.session_state.generating = False
    if "stop_generation" not in st.session_state:
        st.session_state.stop_generation = False

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if st.session_state.generating:
        if st.button("⏹️ Stop Response"):
            st.session_state.stop_generation = True
            st.rerun()

    if prompt := st.chat_input("Ask a legal question..."):
        if not selected_model:
            st.warning("Please select an AI model from the sidebar to chat.")
            st.stop()

        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            full_response = ""
            try:
                st.session_state.generating = True
                st.session_state.stop_generation = False
                
                with st.spinner("Searching knowledge base..."):
                    analyzer = ContractAnalyzer(model_name=selected_model)
                    context = analyzer.query_legal_db(prompt, n_results=rag_limit)

                messages_to_send = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]

                system_prompt = f"""You are 'Insight', an elite Indian Legal AI Advisor.
Answer the user's question with clarity, citing Indian legal principles or statutory provisions where applicable.

--- RETRIEVED KNOWLEDGE BASE CONTEXT ---
{context if (context and "Note:" not in context and "Database Error:" not in context) else "No direct database match found. Rely on general Indian contract law."}
--- END CONTEXT ---
"""
                messages_to_send.insert(0, {"role": "system", "content": system_prompt})
                    
                client = openai.OpenAI(
                    base_url=LLM_API_BASE,
                    api_key=LLM_API_KEY,
                    timeout=LLM_TIMEOUT,
                )
                stream = client.chat.completions.create(
                    model=selected_model,
                    messages=messages_to_send,
                    stream=True
                )
                
                for chunk in stream:
                    if st.session_state.stop_generation:
                        break
                    content = chunk.choices[0].delta.content
                    if content:
                        full_response += content
                        response_placeholder.markdown(full_response + "▌")
                
                response_placeholder.markdown(full_response)
                if full_response:
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
            except openai.APIConnectionError as e:
                st.error(f"LLM Connection Error: Could not reach `{LLM_API_BASE}`.")
            except openai.APIStatusError as e:
                st.error(f"LLM API Error: HTTP {e.status_code} - {e.response}")
            except Exception as e:
                st.error(f"Error during response: {e}")
            finally:
                st.session_state.generating = False
                st.session_state.stop_generation = False
                st.rerun()
