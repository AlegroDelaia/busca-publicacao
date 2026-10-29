import os
import re
import json
import unicodedata
import streamlit as st
from pypdf import PdfReader

# Configuração da página Streamlit
st.set_page_config(
    page_title="Busca de Publicações - BGPM",
    page_icon="🔍",
    layout="wide"
)
# ==============================================================================
# --- CONTROLE DE AUTENTICAÇÃO / LOGIN ---
# ==============================================================================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

def validar_login():
    # Busca do Secrets do Streamlit Cloud (com valores padrão como segurança)
    usuario_correto = st.secrets.get("USUARIO_ACESSO", "caqcg")
    senha_correta = st.secrets.get("SENHA_ACESSO", "senhacaqcg")
    
    if (st.session_state.get("usuario_input") == usuario_correto and 
        st.session_state.get("senha_input") == senha_correta):
        st.session_state.autenticado = True
        # Limpa do estado por segurança
        if "senha_input" in st.session_state:
            del st.session_state.senha_input
    else:
        st.error("Usuário ou senha incorretos.")

if not st.session_state.autenticado:
    st.title("🔒 Acesso Restrito - Busca BGPM")
    st.markdown("Por favor, digite suas credenciais para acessar o sistema.")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.text_input("Usuário:", key="usuario_input")
        st.text_input("Senha:", type="password", key="senha_input")
        st.button("Entrar", on_click=validar_login, use_container_width=True)
        
    st.stop()

st.title("🔍 Busca de Publicações em PDFs")

CACHE_FILE = "pdf_index_cache.json"

# --- GERENCIAMENTO DE ESTADO DA BUSCA E DO RASCUNHO ---
if "ultimo_termo_busca" not in st.session_state:
    st.session_state.ultimo_termo_busca = ""
if "dias_assiduidade" not in st.session_state:
    st.session_state.dias_assiduidade = 0
if "dias_merito" not in st.session_state:
    st.session_state.dias_merito = 0
if "dias_aniversario" not in st.session_state:
    st.session_state.dias_aniversario = 0
if "dias_outros" not in st.session_state:
    st.session_state.dias_outros = 0

# --- FUNÇÕES DE AUXÍLIO E NORMALIZAÇÃO ---
def remover_acentos(texto):
    """Remove acentos e caracteres especiais para busca flexível."""
    if not texto:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def load_index_from_disk():
    """Carrega o índice salvo em arquivo JSON se existir."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_index_to_disk(index_data):
    """Salva o índice compilado em arquivo JSON."""
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False)

@st.cache_data(show_spinner=False)
def sync_pdf_index(folder_path="."):
    """
    Compara os PDFs da pasta com o cache em disco.
    Indexa apenas os PDFs novos ou não indexados.
    """
    disk_cache = load_index_from_disk()
    pdf_files = sorted([f for f in os.listdir(folder_path) if f.lower().endswith(".pdf")])
    
    updated = False
    pending_files = [f for f in pdf_files if f not in disk_cache]

    if pending_files:
        progress_bar = st.sidebar.progress(0)
        status_text = st.sidebar.empty()

        for idx, filename in enumerate(pending_files):
            filepath = os.path.join(folder_path, filename)
            status_text.text(f"Indexando novo PDF ({idx+1}/{len(pending_files)}): {filename}...")
            updated = True
            pages_list = []
            try:
                reader = PdfReader(filepath)
                for page_num, page in enumerate(reader.pages):
                    text = page.extract_text() or ""
                    pages_list.append({
                        "page_num": page_num + 1,
                        "text": text
                    })
                disk_cache[filename] = pages_list
            except Exception as e:
                st.error(f"Erro ao processar {filename}: {e}")

            progress_bar.progress((idx + 1) / len(pending_files))

        status_text.empty()
        progress_bar.empty()

    if updated:
        save_index_to_disk(disk_cache)

    flat_pages = []
    for doc_name, pages in disk_cache.items():
        for page_data in pages:
            flat_pages.append({
                "doc_name": doc_name,
                "page_num": page_data["page_num"],
                "text": page_data["text"]
            })

    return flat_pages, pdf_files

# --- CARREGAMENTO RÁPIDO DO ÍNDICE ---
all_pages, pdf_files = sync_pdf_index()

# --- INTERFACE PRINCIPAL DE BUSCA (POSICIONADA ANTES PARA DETECTAR MUDANÇA) ---
col_input, col_type = st.columns([3, 1])
with col_input:
    search_query = st.text_input("Digite o termo de busca (Ex: NF, nome, etc.):", placeholder="Digite o NF ou nome")
with col_type:
    exact_match = st.checkbox("Busca por palavra exata", value=False)

termo_atual = search_query.strip()

# VERIFICAÇÃO: Se o termo de busca mudou, zera o rascunho de dispensas
if termo_atual != st.session_state.ultimo_termo_busca:
    st.session_state.ultimo_termo_busca = termo_atual
    st.session_state.dias_assiduidade = 0
    st.session_state.dias_merito = 0
    st.session_state.dias_aniversario = 0
    st.session_state.dias_outros = 0

# --- BARRA LATERAL ---
st.sidebar.header("📁 Base de Dados Local")
st.sidebar.success(f"**{len(pdf_files)}** arquivos PDF na pasta.")
st.sidebar.info(f"**{len(all_pages)}** páginas prontas para busca.")

if st.sidebar.button("🔄 Forçar Re-indexação Geral"):
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")

# --- PAINEL CALCULADORA DE DISPENSAS ---
with st.sidebar.form("form_painel_dispensas"):
    st.header("📊 Painel de Dispensas")
    
    st.session_state.dias_assiduidade = st.number_input(
        "Assiduidade (dias):", min_value=0, max_value=365, value=st.session_state.dias_assiduidade, step=1
    )
    st.session_state.dias_merito = st.number_input(
        "Mérito Disciplinar (dias):", min_value=0, max_value=365, value=st.session_state.dias_merito, step=1
    )
    st.session_state.dias_aniversario = st.number_input(
        "Aniversário (dias):", min_value=0, max_value=365, value=st.session_state.dias_aniversario, step=1
    )
    st.session_state.dias_outros = st.number_input(
        "Outros / DSR (dias):", min_value=0, max_value=365, value=st.session_state.dias_outros, step=1
    )
    
    btn_somar = st.form_submit_button("🧮 Somar Rascunho", use_container_width=True)

if btn_somar:
    total_dias = (
        st.session_state.dias_assiduidade + 
        st.session_state.dias_merito + 
        st.session_state.dias_aniversario + 
        st.session_state.dias_outros
    )
    st.sidebar.success(f"🏆 **Saldo Total:** {total_dias} dia(s)")

# --- PROCESSAMENTO E EXIBIÇÃO DOS RESULTADOS ---
if termo_atual:
    query_norm = remover_acentos(termo_atual)
    results = []

    for page_data in all_pages:
        text = page_data["text"]
        text_norm = remover_acentos(text)
        
        if exact_match:
            match = re.search(r'\b' + re.escape(query_norm) + r'\b', text_norm, re.IGNORECASE)
        else:
            match = query_norm.lower() in text_norm.lower()
            
        if match:
            results.append(page_data)

    st.subheader(f"Total de {len(results)} página(s) localizada(s)")

    if results:
        for item in results:
            doc_name = item["doc_name"]
            page_num = item["page_num"]
            full_text = item["text"]

            pattern = re.compile(re.escape(termo_atual), re.IGNORECASE)
            match = pattern.search(full_text)
            
            if match:
                start_idx = max(0, match.start() - 100)
                end_idx = min(len(full_text), match.end() + 100)
                snippet = full_text[start_idx:end_idx].replace("\n", " ")
                
                highlighted_snippet = pattern.sub(
                    lambda m: f"<mark style='background-color: #ffeb3b; color: #000; font-weight: bold;'>{m.group(0)}</mark>",
                    snippet
                )
            else:
                highlighted_snippet = full_text[:200] + "..."

            title = f"📄 **{doc_name}** — Página **{page_num}**"
            with st.expander(title):
                st.markdown(f"**Trecho encontrado:** ...{highlighted_snippet}...", unsafe_allow_html=True)
                st.divider()
                
                st.markdown("**Conteúdo completo da página:**")
                highlighted_full_text = pattern.sub(
                    lambda m: f"<mark style='background-color: #ffeb3b; color: #000; font-weight: bold;'>{m.group(0)}</mark>",
                    full_text
                )
                
                st.markdown(
                    f"<div style='background-color: #f9f9f9; color: #222; padding: 15px; border-radius: 5px; max-height: 400px; overflow-y: auto; white-space: pre-wrap; font-family: monospace;'>{highlighted_full_text}</div>",
                    unsafe_allow_html=True
                )
    else:
        st.warning("Nenhum resultado encontrado para a busca informada.")
else:
    st.info("💡 Digite um número de NF, nome ou termo no campo acima para buscar.")