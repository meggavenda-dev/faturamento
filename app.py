
# ============================================================
#  APP.PY — MANUAL DE FATURAMENTO (VERSÃO PREMIUM)
#  ORGANIZADO • OTIMIZADO • SEGURO • COM ID ÚNICO
# ============================================================

# ------------------------------------------------------------
# 1. IMPORTS
# ------------------------------------------------------------
import streamlit as st
import requests
import base64
import json
import os
import pandas as pd
from fpdf import FPDF
import unicodedata
import re
import uuid
import time

from github_database import GitHubJSON

# ------------------------------------------------------------
# 2. CONFIGURAÇÃO DE ACESSO (SECRETS)
# ------------------------------------------------------------
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_OWNER = st.secrets["REPO_OWNER"]
    REPO_NAME = st.secrets["REPO_NAME"]
except Exception:
    st.error("⚠️ Configure os Secrets: GITHUB_TOKEN, REPO_OWNER e REPO_NAME.")
    st.stop()

FILE_PATH = "dados.json"
BRANCH = "main"

db = GitHubJSON(
    token=GITHUB_TOKEN,
    owner=REPO_OWNER,
    repo=REPO_NAME,
    path=FILE_PATH,
    branch=BRANCH
)


# ------------------------------------------------------------
# 3. CONSTANTES / PALETA
# ------------------------------------------------------------
PRIMARY_COLOR = "#1F497D"
PRIMARY_LIGHT = "#E8EEF5"
BG_LIGHT = "#F5F7FA"
GREY_BORDER = "#D9D9D9"
TEXT_DARK = "#2D2D2D"

VERSOES_TISS = [
    "Não Envia",
    "4.03.00",
    "4.02.00",
    "4.01.00",
    "01.06.00",
    "3.05.00",
    "3.04.01"
]

EMPRESAS_FATURAMENTO = ["Integralis", "AMHP", "Outros"]

SISTEMAS = ["Outros", "Orizon", "Benner", "Maida", "Facil", "Visual TISS", "Próprio"]


# Opções oficiais (validação estrita)
OPCOES_XML = ["Sim", "Não"]
OPCOES_NF = ["Sim", "Não"]
OPCOES_FLUXO_NF = ["Envia XML sem nota", "Envia NF junto com o lote"]


# ------------------------------------------------------------
# 4. CSS GLOBAL + HEADER FIXO
# ------------------------------------------------------------
CSS_GLOBAL = f"""
<style>

    /* Ajuste geral */
    .block-container {{
        padding-top: 6rem !important;
        max-width: 1200px !important;
    }}

    /* HEADER */
    .header-premium {{
        position: fixed;
        top: 0; left: 0;
        width: 100%; height: 70px;
        background: rgba(255,255,255,0.85);
        backdrop-filter: blur(10px);
        border-bottom: 1px solid {PRIMARY_COLOR}33;
        display: flex; align-items: center;
        padding: 0 40px;
        z-index: 999;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
    }}

    .header-title {{
        font-size: 24px;
        font-weight: 700;
        color: {PRIMARY_COLOR};
        letter-spacing: -0.5px;
        display: flex; align-items: center; gap: 10px;
    }}

    /* Cards estilo Microsoft */
    .card {{
        background: #ffffff;
        padding: 24px;
        border-radius: 8px;
        border: 1px solid #e1e4e8;
        box-shadow: 0 4px 6px rgba(0,0,0,0.03);
        margin-bottom: 24px;
        transition: transform 0.15s, box-shadow 0.15s;
    }}

    .card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 6px 14px rgba(0,0,0,0.06);
    }}

    .card-title {{
        font-size: 20px;
        font-weight: 700;
        margin-bottom: 15px;
        color: {PRIMARY_COLOR};
    }}

    /* Botões */
    .stButton > button {{
        background-color: {PRIMARY_COLOR} !important;
        color: white !important;
        border-radius: 6px !important;
        padding: 8px 18px !important;
        font-weight: 600 !important;
        border: none !important;
    }}

    .stButton > button:hover {{
        background-color: #16375E !important;
    }}

</style>

<div class="header-premium">
    <span class="header-title">💼 Manual de Faturamento</span>
</div>
"""

st.markdown(CSS_GLOBAL, unsafe_allow_html=True)


# ============================================================
# 5. FUNÇÕES UTILITÁRIAS
# ============================================================

def normalize(value):
    if not value:
        return ""
    return sanitize_text(value).strip().lower()


def generate_id(dados_atuais):
    """Gera ID sequencial robusto (ignora IDs inválidos ou ausentes)."""
    ids = []

    for item in dados_atuais:
        try:
            id_val = int(item.get("id"))
            if id_val > 0:
                ids.append(id_val)
        except:
            continue

    return max(ids) + 1 if ids else 1



def sanitize_text(text: str) -> str:
    """
    Normaliza strings removendo caracteres invisíveis, unicode corrompido
    e retornando sempre uma string segura para PDF e interface.
    """
    if text is None:
        return ""

    txt = str(text)
    txt = unicodedata.normalize("NFKD", txt)

    # Remove caracteres invisíveis e de controle
    txt = re.sub(r"[\u200B-\u200F\u202A-\u202E\u2060-\u206F]", "", txt)
    txt = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", txt)

    return txt.replace("\r", "").strip()


def safe_get(d: dict, key: str, default=""):
    """
    Acesso seguro a dicionários.
    Evita erros quando dados estão faltando ou o convênio é novo.
    """
    if not isinstance(d, dict):
        return default
    return sanitize_text(d.get(key, default))


def chunk_text(text, size):
    """
    Divide palavras extremamente longas para PDF.
    Garante que o 'size' seja sempre um inteiro para o range.
    """
    text = sanitize_text(text or "")
    # Garante que o passo do range seja int e no mínimo 1
    safe_size = int(size) if size >= 1 else 1 
    return [text[i:i+safe_size] for i in range(0, len(text), safe_size)]


def wrap_text(text, pdf, max_width):
    text = sanitize_text(text)
    if not text:
        return [""]

    words = text.split(" ")
    lines, current = [], ""

    for w in words:
        if pdf.get_string_width(w) > max_width:
            if current:
                lines.append(current)
                current = ""
            
            # Força a divisão para inteiro
            size = int(max(1, max_width // 3)) 
            lines.extend(chunk_text(w, size))
            continue

        candidate = f"{current} {w}".strip() if current else w
        if pdf.get_string_width(candidate) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = w

    if current:
        lines.append(current)

    return lines


# ============================================================
# 7. GERAÇÃO DO PDF — VERSÃO ORGANIZADA, PROFISSIONAL E ESTÁVEL
# ============================================================

def gerar_pdf(dados):
    """
    Versão Fiel ao Modelo ASTE: Layout limpo, minimalista e 
    com posicionamento preciso dos campos de acesso.
    """
    pdf = FPDF()
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Fontes com Fallback
    try:
        pdf.add_font("DejaVu", "", "DejaVuSans.ttf", uni=True)
        pdf.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf", uni=True)
        FONT_MAIN = "DejaVu"
    except:
        FONT_MAIN = "Arial"

    W_TOTAL = pdf.w - 30 

    # --- TÍTULO PRINCIPAL ---
    pdf.set_font(FONT_MAIN, "B", 14)
    pdf.cell(W_TOTAL, 10, f"GUIA TÉCNICA: {safe_get(dados,'nome').upper()}", ln=1, align="L")
    pdf.ln(5)

    # --- 1. DADOS DE IDENTIFICAÇÃO E ACESSO ---
    pdf.set_font(FONT_MAIN, "B", 11)
    pdf.cell(W_TOTAL, 8, "1. DADOS DE IDENTIFICAÇÃO E ACESSO", ln=1)
    pdf.ln(2)
    
    # Grid de Identificação (Limpo)
    def add_line(label, value):
        pdf.set_font(FONT_MAIN, "B", 10)
        pdf.cell(20, 7, label, border=0)
        pdf.set_font(FONT_MAIN, "", 10)
        pdf.cell(W_TOTAL - 20, 7, value, ln=1)

    add_line("Empresa:", safe_get(dados, "empresa"))
    add_line("Portal:", safe_get(dados, "site"))
    add_line("Login:", safe_get(dados, "login"))
    add_line("Sistema:", safe_get(dados, "sistema_utilizado"))
    pdf.ln(5)

    # --- 2. CRONOGRAMA E REGRAS TÉCNICAS ---
    pdf.set_font(FONT_MAIN, "B", 11)
    pdf.cell(W_TOTAL, 8, "2. CRONOGRAMA E REGRAS TÉCNICAS", ln=1)
    pdf.ln(2)

    # Tabela (Linhas Pretas Finas)
    widths = [35, 30, 40, 25, 50]
    headers = ["Prazo Envio", "Validade Guia", "XML/Versão", "Nota Fiscal", "Fluxo NF"]
    
    pdf.set_font(FONT_MAIN, "B", 9)
    for i, h in enumerate(headers):
        pdf.cell(widths[i], 8, h, border=1, align="C")
    pdf.ln()

    pdf.set_font(FONT_MAIN, "", 9)
    y_tab = pdf.get_y()
    row_vals = [
        safe_get(dados, "envio"),
        f"{safe_get(dados, 'validade')} dias",
        f"{safe_get(dados, 'xml')} / {safe_get(dados, 'versao_xml')}",
        safe_get(dados, "nf"),
        safe_get(dados, "fluxo_nf")
    ]
    
    for i, val in enumerate(row_vals):
        pdf.set_xy(pdf.l_margin + sum(widths[:i]), y_tab)
        pdf.multi_cell(widths[i], 6, val, border=1, align="C")
    
    # Espaçamento após tabela
    pdf.set_y(y_tab + 15)

    # --- CAMPOS ABAIXO DA TABELA (Exatamente como no PDF da ASTE) ---
    pdf.set_font(FONT_MAIN, "B", 10)
    pdf.write(7, "Código: ")
    pdf.set_font(FONT_MAIN, "", 10)
    pdf.write(7, safe_get(dados, "codigo"))
    pdf.ln(7)

    pdf.set_font(FONT_MAIN, "B", 10)
    pdf.write(7, "Senha: ")
    pdf.set_font(FONT_MAIN, "", 10)
    pdf.write(7, safe_get(dados, "senha"))
    pdf.ln(7)

    pdf.set_font(FONT_MAIN, "B", 10)
    pdf.write(7, "Retorno: ")
    pdf.set_font(FONT_MAIN, "", 10)
    pdf.write(7, safe_get(dados, "prazo_retorno"))
    pdf.ln(12)

    # --- SEÇÕES DE TEXTO ---
    def add_simple_section(title, key):
        content = safe_get(dados, key)
        if content and content.strip():
            pdf.set_font(FONT_MAIN, "B", 11)
            pdf.cell(W_TOTAL, 8, title, ln=1)
            pdf.ln(1)
            pdf.set_font(FONT_MAIN, "", 10)
            pdf.multi_cell(W_TOTAL, 6, content)
            pdf.ln(6)

    add_simple_section("OBSERVAÇÕES CRÍTICAS", "observacoes")
    add_simple_section("DIGITALIZAÇÃO E DOCUMENTAÇÃO", "doc_digitalizacao")

    # RODAPÉ - Centralizado e Simples
    pdf.set_y(-20)
    pdf.set_font(FONT_MAIN, "", 10)
    pdf.cell(W_TOTAL, 10, "Manual de Faturamento GABMA", align="C")

    return pdf.output(dest="S").encode("latin-1")

# ============================================================
# 8. COMPONENTES DE INTERFACE (UI COMPONENTS)
# ============================================================

def ui_card_start(title: str):
    """Inicia um card estilizado (versão Microsoft)."""
    st.markdown(f"""
        <div class='card'>
            <div class='card-title'>{sanitize_text(title)}</div>
    """, unsafe_allow_html=True)


def ui_card_end():
    """Fecha um card."""
    st.markdown("</div>", unsafe_allow_html=True)


def ui_section_title(text: str):
    """Título centralizado para páginas completas."""
    st.markdown(
        f"""
        <div style="
            margin-top:20px;
            padding:25px;
            text-align:center;
            color:white;
            background:{PRIMARY_COLOR};
            border-radius:10px;
            font-size:26px;
            font-weight:700;">
            {sanitize_text(text).upper()}
        </div>
        """,
        unsafe_allow_html=True
    )


def ui_info_line(label: str, value: str):
    """Linha padrão 'Label: Valor' com layout moderno."""
    st.markdown(
        f"""
        <div style="
            margin:6px 0;
            font-size:15px;
            line-height:1.5;">
            <strong>{sanitize_text(label)}:</strong>
            <span style="color:{TEXT_DARK};"> {sanitize_text(value)} </span>
        </div>
        """,
        unsafe_allow_html=True
    )


def ui_block_info(title: str, content: str):
    """Exibe blocos de conteúdo longo com destaque lateral."""
    if not content:
        return

    ui_card_start(title)

    st.markdown(
        f"""
        <div style="
            background-color:white;
            border-left:4px solid {PRIMARY_COLOR};
            padding:12px 16px;
            border-radius:6px;
            font-size:15px;
            line-height:1.5;">
            {sanitize_text(content).replace("\n", "<br>")}
        </div>
        """,
        unsafe_allow_html=True,
    )

    ui_card_end()


# ============================================================
# 9. PÁGINA — CADASTRO / EDIÇÃO DE CONVÊNIOS
# ============================================================

def page_cadastro():
    """
    Página de cadastro totalmente corrigida:
    - Sempre recarrega do GitHub (nunca usa lista mutável da sessão)
    - Usa cópia real dos dados
    - Salva com atomicidade
    - Atualiza imediatamente as telas
    """

    # 🔥 Recarrega sempre dados frescos do GitHub
    dados_atuais, _ = db.load(force=True)
    dados_atuais = list(dados_atuais)  # segurança contra mutação

    ui_card_start("📝 Cadastro de Convênio")

    # Lista com ID + Nome
    opcoes = ["+ Novo Convênio"] + [
        f"{c.get('id')} — {safe_get(c, 'nome')}" for c in dados_atuais
    ]

    escolha = st.selectbox("Selecione um convênio para editar:", opcoes)

    if escolha == "+ Novo Convênio":
        conv_id = None
        dados_conv = None
    else:
        conv_id = escolha.split(" — ")[0]
        dados_conv = next(
            (c for c in dados_atuais if str(c.get("id")) == str(conv_id)),
            None
        )

    ui_card_end()

    # --------------------------------------------
    # FORMULÁRIO
    # --------------------------------------------
    form_key = f"form_{conv_id}" if conv_id else "form_novo"

    with st.form(key=form_key):


        col1, col2, col3 = st.columns(3)

        # COLUNA 1
        with col1:
            nome = st.text_input("Nome do Convênio", value=safe_get(dados_conv, "nome"))
            codigo = st.text_input("Código", value=safe_get(dados_conv, "codigo"))

            
            valor_empresa = safe_get(dados_conv, "empresa")
            if valor_empresa not in EMPRESAS_FATURAMENTO:
                valor_empresa = EMPRESAS_FATURAMENTO[0]
            
            empresa = st.selectbox(
                "Empresa Faturamento",
                EMPRESAS_FATURAMENTO,
                index=EMPRESAS_FATURAMENTO.index(valor_empresa)
            )


            
            valor_sistema = safe_get(dados_conv, "sistema_utilizado")
            if valor_sistema not in SISTEMAS:
                valor_sistema = SISTEMAS[0]
            
            sistema = st.selectbox(
                "Sistema",
                SISTEMAS,
                index=SISTEMAS.index(valor_sistema)
            )


        # COLUNA 2
        with col2:
            site = st.text_input("Site/Portal", value=safe_get(dados_conv, "site"))
            login = st.text_input("Login", value=safe_get(dados_conv, "login"))
            senha = st.text_input("Senha", value=safe_get(dados_conv, "senha"))
            retorno = st.text_input("Prazo Retorno", value=safe_get(dados_conv, "prazo_retorno"))

        # COLUNA 3
        with col3:
            envio = st.text_input("Prazo Envio", value=safe_get(dados_conv, "envio"))
            validade = st.text_input("Validade da Guia", value=safe_get(dados_conv, "validade"))

            
            valor_xml = safe_get(dados_conv, "xml")
            if valor_xml not in OPCOES_XML:
                valor_xml = "Sim"
            
            xml = st.radio(
                "Envia XML?",
                OPCOES_XML,
                index=OPCOES_XML.index(valor_xml)
            )


            
            valor_nf = safe_get(dados_conv, "nf")
            if valor_nf not in OPCOES_NF:
                valor_nf = "Sim"
            
            nf = st.radio(
                "Exige Nota Fiscal?",
                OPCOES_NF,
                index=OPCOES_NF.index(valor_nf)
            )


        # XML/NF
        colA, colB = st.columns(2)

        with colA:
            
            valor_versao = safe_get(dados_conv, "versao_xml")
            if valor_versao not in VERSOES_TISS:
                valor_versao = VERSOES_TISS[0]
            
            versao_xml = st.selectbox(
                "Versão XML (TISS)",
                VERSOES_TISS,
                index=VERSOES_TISS.index(valor_versao)
            )


        with colB:
            
            valor_fluxo = safe_get(dados_conv, "fluxo_nf")
            if valor_fluxo not in OPCOES_FLUXO_NF:
                valor_fluxo = OPCOES_FLUXO_NF[0]
            
            fluxo_nf = st.selectbox(
                "Fluxo da Nota",
                OPCOES_FLUXO_NF,
                index=OPCOES_FLUXO_NF.index(valor_fluxo)
            )

        config_gerador = st.text_area(
            "Configuração do Gerador XML",
            value=safe_get(dados_conv, "config_gerador"),
        )
        doc_digitalizacao = st.text_area(
            "Digitalização e Documentação",
            value=safe_get(dados_conv, "doc_digitalizacao"),
        )
        observacoes = st.text_area(
            "Observações Críticas",
            value=safe_get(dados_conv, "observacoes"),
        )

        submit = st.form_submit_button("💾 Salvar Dados")

        if submit:

            # MONTA REGISTRO
            novo_registro = {
                "nome": nome,
                "codigo": codigo,
                "empresa": empresa,
                "sistema_utilizado": sistema,
                "site": site,
                "login": login,
                "senha": senha,
                "prazo_retorno": retorno,
                "envio": envio,
                "validade": validade,
                "xml": xml,
                "nf": nf,
                "versao_xml": versao_xml,
                "fluxo_nf": fluxo_nf,
                "config_gerador": config_gerador,
                "doc_digitalizacao": doc_digitalizacao,
                "observacoes": observacoes,
            }

            # NOVO OU EXISTENTE
            if conv_id is None:
                novo_registro["id"] = generate_id(dados_atuais)
                dados_atuais.append(novo_registro)

            else:
                novo_registro["id"] = int(conv_id)
                for i, c in enumerate(dados_atuais):
                    if str(c.get("id")) == str(conv_id):
                        dados_atuais[i] = novo_registro
                        break

            # SALVAR NO GITHUB
            if db.save(dados_atuais):

                st.success(f"✔ Convênio {novo_registro['id']} salvo com sucesso!")

                # LIMPA CACHE DO BANCO                
                db._cache_data = None
                db._cache_sha = None
                db._cache_etag = None
                db._cache_timestamp = 0


                # LIMPA ESTADO DO STREAMLIT (o segredo!)
                st.session_state.clear()

                time.sleep(1)
                st.rerun()

    # BOTÃO PDF
    if dados_conv:
        st.download_button(
            "📥 Baixar PDF do Convênio",
            gerar_pdf(dados_conv),
            file_name=f"Manual_{safe_get(dados_conv,'nome')}.pdf",
            mime="application/pdf"
        )
              

# ============================================================
# 10. PÁGINA — CONSULTA DE CONVÊNIOS
# ============================================================


def page_consulta(dados_atuais):

    if not dados_atuais:
        st.info("Nenhum convênio cadastrado.")
        return

    # Lista segura: caso falte ID
    opcoes = sorted([
        f"{safe_get(c,'id')} || {safe_get(c,'nome')}"
        for c in dados_atuais
    ])

    escolha = st.selectbox("Selecione o convênio:", opcoes)

    # Extrai ID de forma segura
    conv_id = escolha.split(" || ")[0]

    # Evita StopIteration
    dados = next((c for c in dados_atuais if safe_get(c,"id") == conv_id), None)

    if not dados:
        st.error("Erro: convênio não encontrado no banco.")
        return

    # Título grande
    ui_section_title(safe_get(dados, "nome"))

    # ------------- DADOS DE IDENTIFICAÇÃO -------------
    ui_card_start("🧾 Dados de Identificação")
    ui_info_line("Empresa", safe_get(dados, "empresa"))
    ui_info_line("Código", safe_get(dados, "codigo"))
    ui_info_line("Sistema", safe_get(dados, "sistema_utilizado"))
    ui_info_line("Prazo de Retorno", safe_get(dados, "prazo_retorno"))
    ui_card_end()

    # ------------- ACESSO AO PORTAL -------------------
    ui_card_start("🔐 Acesso ao Portal")
    ui_info_line("Portal", safe_get(dados, "site"))
    ui_info_line("Login", safe_get(dados, "login"))
    ui_info_line("Senha", safe_get(dados, "senha"))
    ui_card_end()

    # ------------- REGRAS TÉCNICAS --------------------
    ui_card_start("📦 Regras Técnicas")
    ui_info_line("Prazo Envio", safe_get(dados, "envio"))
    ui_info_line("Validade da Guia", safe_get(dados, "validade"))
    ui_info_line("Envia XML?", safe_get(dados, "xml"))
    ui_info_line("Versão XML", safe_get(dados, "versao_xml"))
    ui_info_line("Exige NF?", safe_get(dados, "nf"))
    ui_info_line("Fluxo da Nota", safe_get(dados, "fluxo_nf"))
    ui_card_end()

    # ------------- BLOCOS EXTRAS ----------------------
    ui_block_info("⚙️ Configuração XML", safe_get(dados, "config_gerador"))
    ui_block_info("🗂 Digitalização e Documentação", safe_get(dados, "doc_digitalizacao"))
    ui_block_info("⚠️ Observações Críticas", safe_get(dados, "observacoes"))

    st.caption("Manual de Faturamento — Visualização Premium")



# ============================================================
# 11. PÁGINA — VISUALIZAR TODO O BANCO
# ============================================================

def page_visualizar_banco(dados_atuais):

    ui_card_start("📋 Banco de Dados Completo")

    if dados_atuais:
        df = pd.DataFrame(dados_atuais)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("⚠️ Banco vazio.")

    ui_card_end()


# ============================================================
# 12. MAIN APP — ROTEAMENTO, CARREGAMENTO E ESTRUTURA FINAL
# ============================================================

def main():
    st.set_page_config(
        page_title="💼 Manual de Faturamento",
        layout="wide"
    )

    # --------------------------------------------------------
    # CARREGAR BANCO DO GITHUB
    # --------------------------------------------------------
    dados_atuais, sha_atual = db.load()

    # --------------------------------------------------------
    # SIDEBAR — Navegação
    # --------------------------------------------------------
    st.sidebar.title("📚 Navegação")

    menu = st.sidebar.radio(
        "Selecione a página:",
        [
            "Cadastrar / Editar",
            "Consulta de Convênios",
            "Visualizar Banco"
        ]
    )

    st.sidebar.markdown("---")

    st.sidebar.markdown("### 🔄 Atualizar Sistema")
    if st.sidebar.button("Recarregar"):
        st.rerun()

    # --------------------------------------------------------
    # ROTEAMENTO DAS PÁGINAS
    # --------------------------------------------------------
    if menu == "Cadastrar / Editar":
        page_cadastro()

    elif menu == "Consulta de Convênios":
        page_consulta(dados_atuais)

    elif menu == "Visualizar Banco":
        page_visualizar_banco(dados_atuais)

    # --------------------------------------------------------
    # Rodapé Premium
    # --------------------------------------------------------
    st.markdown(
        f"""
        <br><br>
        <div style='text-align:center; color:#777; font-size:13px; padding:10px;'>
            © 2026 — Manual de Faturamento GABMA<br>
            Desenvolvido com design corporativo Microsoft/MV
        </div>
        """,
        unsafe_allow_html=True
    )


# Executar aplicação
if __name__ == "__main__":
    main()


