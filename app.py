
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

def generate_id(dados_atuais):
    """
    Gera um ID decimal sequencial baseado no maior ID existente.
    Se a lista estiver vazia, começa em 1.
    """
    if not dados_atuais:
        return 1
    
    ids = []
    for item in dados_atuais:
        try:
            # Tenta converter o ID existente para int (caso ainda existam UUIDs antigos)
            ids.append(int(item.get("id", 0)))
        except ValueError:
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
    Divide palavras extremamente longas (sem espaços) para PDF.
    """
    text = sanitize_text(text or "")
    return [text[i:i+size] for i in range(0, len(text), size)]


def wrap_text(text, pdf, max_width):
    """
    Quebra texto para PDF respeitando o limite de largura real.
    """
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
            lines.extend(chunk_text(w, max_width // 3))
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
# 6. FUNÇÕES GITHUB — CRUD PREMIUM SEGURO (ID + SHA DINÂMICO)
# ============================================================

def github_get_file():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}?ref={BRANCH}&t={int(time.time())}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            content = response.json()
            decoded = base64.b64decode(content["content"]).decode("utf-8")
            data = json.loads(decoded)
            
            # Migração para ID Decimal (Garante que strings virem números)
            modified = False
            for i, item in enumerate(data):
                if "id" not in item or isinstance(item["id"], str):
                    item["id"] = i + 1
                    modified = True
            
            if modified:
                github_save_file(data, content["sha"])
            return data, content["sha"]
        
        elif response.status_code == 404:
            return [], None
        else:
            st.error(f"⚠️ Erro GitHub: {response.status_code}")
            return [], None
    except Exception as e:
        st.error(f"❌ Erro ao consultar GitHub: {e}")
        return [], None


def github_save_file(data, previous_sha):
    """
    Salva o JSON atualizado no GitHub utilizando o SHA mais recente possível.
    Evita erros 409 (Conflict) e garante consistência.
    """
    # 🔍 Sempre pega o SHA mais recente
    _, latest_sha = github_get_file()
    sha_to_use = latest_sha or previous_sha

    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        json_string = json.dumps(data, indent=4, ensure_ascii=False)
        encoded = base64.b64encode(json_string.encode("utf-8")).decode("utf-8")

        payload = {
            "message": "Update Manual de Faturamento — GABMA",
            "content": encoded,
            "branch": BRANCH,
            "sha": sha_to_use
        }

        response = requests.put(url, headers=headers, json=payload)

        if response.status_code in (200, 201):
            return True

        st.error(f"❌ Erro GitHub {response.status_code}: {response.text}")
        return False

    except Exception as e:
        st.error(f"❌ Falha ao salvar no GitHub: {e}")
        return False


# ============================================================
# 7. GERAÇÃO DO PDF — VERSÃO ORGANIZADA, PROFISSIONAL E ESTÁVEL
# ============================================================

def gerar_pdf(dados):
    """
    Gera PDF técnico detalhado do convênio utilizando FPDF.
    Inclui seções, tabelas, quebras inteligentes e layout corporativo.
    """

    pdf = FPDF()
    pdf.set_margins(10, 10, 10)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # --------------------------------------------------------
    # CONFIGURAÇÃO DE FONTES
    # --------------------------------------------------------
    fonte_normal = "DejaVuSans.ttf"
    fonte_bold = "DejaVuSans-Bold.ttf"

    has_normal = os.path.exists(fonte_normal)
    has_bold = os.path.exists(fonte_bold)

    if has_normal:
        pdf.add_font("DejaVu", "", fonte_normal, uni=True)
        if has_bold:
            pdf.add_font("DejaVu", "B", fonte_bold, uni=True)
        FONT = "DejaVu"
    else:
        FONT = "Helvetica"

    def set_font(size=10, bold=False):
        style = "B" if bold else ""
        try:
            pdf.set_font(FONT, style, size)
        except:
            pdf.set_font("Helvetica", style, size)

    CONTENT_WIDTH = pdf.w - pdf.l_margin - pdf.r_margin

    # --------------------------------------------------------
    # FUNÇÕES AUXILIARES DO PDF
    # --------------------------------------------------------

    def cell_label_value(label, value, label_w=40, h=7):
        """Linha 'Label: Valor' com quebra automática."""
        label = sanitize_text(label)
        value = sanitize_text(value)

        set_font(9, True)
        pdf.cell(label_w, h, f"{label}:")
        set_font(9, False)

        usable = CONTENT_WIDTH - label_w

        if pdf.get_string_width(value) <= usable:
            pdf.cell(usable, h, value, ln=1)
        else:
            lines = wrap_text(value, pdf, usable)
            pdf.cell(usable, h, lines[0], ln=1)
            for ln_text in lines[1:]:
                pdf.set_x(pdf.l_margin + label_w)
                pdf.cell(usable, h, ln_text, ln=1)

    def two_cols(label1, val1, label2, val2, label_w=38, gap=6, h=7):
        """Duas colunas lado a lado com quebra automática."""
        col_width = (CONTENT_WIDTH - gap) / 2

        val1 = sanitize_text(val1)
        val2 = sanitize_text(val2)

        lines_left = wrap_text(val1, pdf, col_width - label_w)
        lines_right = wrap_text(val2, pdf, col_width - label_w)
        max_lines = max(len(lines_left), len(lines_right))
        row_h = max_lines * h

        if pdf.get_y() + row_h > pdf.page_break_trigger:
            pdf.add_page()

        y_start = pdf.get_y()

        # Coluna esquerda
        set_font(9, True)
        pdf.set_xy(pdf.l_margin, y_start)
        pdf.cell(label_w, h, f"{label1}:")
        set_font(9, False)
        x_start_left = pdf.get_x()
        for i, txt in enumerate(lines_left):
            pdf.set_xy(x_start_left, y_start + i * h)
            pdf.cell(col_width - label_w, h, txt)

        # Coluna direita
        x_right = pdf.l_margin + col_width + gap
        set_font(9, True)
        pdf.set_xy(x_right, y_start)
        pdf.cell(label_w, h, f"{label2}:")
        set_font(9, False)
        x_start_right = pdf.get_x()
        for i, txt in enumerate(lines_right):
            pdf.set_xy(x_start_right, y_start + i * h)
            pdf.cell(col_width - label_w, h, txt)

        pdf.set_y(y_start + row_h)

    def table_row(widths, values, aligns=None, h=6):
        """Linha de tabela com bordas, múltiplas linhas e altura uniforme."""
        aligns = aligns or ["L"] * len(widths)

        processed = [wrap_text(v, pdf, widths[i] - 2) for i, v in enumerate(values)]
        max_lines = max(len(col) for col in processed)
        row_h = max_lines * h

        if pdf.get_y() + row_h > pdf.page_break_trigger:
            pdf.add_page()

        x0 = pdf.get_x()
        y0 = pdf.get_y()

        for i, width in enumerate(widths):
            x = pdf.get_x()
            pdf.rect(x, y0, width, row_h)
            for j, line in enumerate(processed[i]):
                pdf.set_xy(x + 1, y0 + j * h)
                pdf.cell(width - 2, h, line, align=aligns[i])
            pdf.set_x(x + width)

        pdf.set_xy(x0, y0 + row_h)

    # --------------------------------------------------------
    # CABEÇALHO PRINCIPAL
    # --------------------------------------------------------
    pdf.set_fill_color(31, 73, 125)
    pdf.set_text_color(255, 255, 255)
    set_font(16, True)

    nome_conv = safe_get(dados, "nome").upper()
    pdf.cell(0, 15, f"GUIA TÉCNICA: {nome_conv}", ln=True, align="C", fill=True)

    pdf.ln(4)
    pdf.set_text_color(0, 0, 0)

    # --------------------------------------------------------
    # SEÇÃO 1 — IDENTIFICAÇÃO
    # --------------------------------------------------------
    pdf.set_fill_color(230, 230, 230)
    set_font(11, True)
    pdf.cell(0, 8, " 1. DADOS DE IDENTIFICAÇÃO E ACESSO", ln=True, fill=True)
    pdf.ln(2)

    two_cols("Empresa", safe_get(dados, "empresa"),
             "Código", safe_get(dados, "codigo"))

    cell_label_value("Portal", safe_get(dados, "site"))

    two_cols("Login", safe_get(dados, "login"),
             "Senha", safe_get(dados, "senha"))

    two_cols("Sistema", safe_get(dados, "sistema_utilizado"),
             "Retorno", safe_get(dados, "prazo_retorno"))

    pdf.ln(4)

    # --------------------------------------------------------
    # SEÇÃO 2 — REGRAS TÉCNICAS (TABELA)
    # --------------------------------------------------------
    pdf.set_fill_color(230, 230, 230)
    set_font(11, True)
    pdf.cell(0, 8, " 2. CRONOGRAMA E REGRAS TÉCNICAS", ln=True, fill=True)
    pdf.ln(2)

    headers = ["Prazo Envio", "Validade Guia", "XML / Versão", "Nota Fiscal", "Fluxo NF"]
    widths = [40, 30, 32, 30, 60]
    aligns = ["C"] * 5

    set_font(9, True)
    table_row(widths, headers, aligns=aligns, h=7)

    set_font(9, False)
    xml_flag = safe_get(dados, "xml")
    xml_ver = safe_get(dados, "versao_xml")

    table_row(
        widths,
        [
            safe_get(dados, "envio"),
            f"{safe_get(dados, 'validade')} dias" if safe_get(dados, "validade") else "—",
            f"{xml_flag} / {xml_ver}",
            safe_get(dados, "nf"),
            safe_get(dados, "fluxo_nf")
        ],
        aligns=aligns,
        h=7
    )

    pdf.ln(5)

    # --------------------------------------------------------
    # SEÇÃO 3 — BLOCOS EXTRAS
    # --------------------------------------------------------
    def bloco(titulo, campo):
        texto = safe_get(dados, campo)
        if not texto:
            return

        pdf.set_fill_color(240, 240, 240)
        set_font(11, True)
        pdf.cell(0, 7, f" {titulo}", ln=True, fill=True)

        set_font(9, False)
        pdf.multi_cell(0, 5, texto, border=1)
        pdf.ln(3)

    bloco("CONFIGURAÇÃO DO GERADOR XML", "config_gerador")
    bloco("DIGITALIZAÇÃO E DOCUMENTAÇÃO", "doc_digitalizacao")
    bloco("OBSERVAÇÕES CRÍTICAS", "observacoes")

    # --------------------------------------------------------
    # RODAPÉ
    # --------------------------------------------------------
    pdf.set_y(-20)
    set_font(8, False)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 10, "Manual de Faturamento — GABMA", align="C")

    return bytes(pdf.output())


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

def page_cadastro(dados_atuais, sha_atual):

    ui_card_start("📝 Cadastro de Convênio")

    # Lista com ID + Nome para garantir segurança
    opcoes = ["+ Novo Convênio"] + [
        f"{c['id']} — {safe_get(c, 'nome')}" for c in dados_atuais
    ]

    escolha = st.selectbox("Selecione um convênio:", opcoes)

    # Determina ID real escolhido
    if escolha == "+ Novo Convênio":
        conv_id = None
        dados_conv = None
    else:
        conv_id = escolha.split(" — ")[0]
        dados_conv = next((c for c in dados_atuais if c["id"] == conv_id), None)

    ui_card_end()

    # --------------------------------------------------------
    # FORMULÁRIO COMPLETO
    # --------------------------------------------------------
    with st.form("form_cadastro"):

        col1, col2, col3 = st.columns(3)

        # ---------------------- COLUNA 1 ----------------------
        with col1:
            nome = st.text_input("Nome do Convênio", value=safe_get(dados_conv, "nome"))
            codigo = st.text_input("Código", value=safe_get(dados_conv, "codigo"))

            empresa = st.selectbox(
                "Empresa Faturamento",
                EMPRESAS_FATURAMENTO,
                index=EMPRESAS_FATURAMENTO.index(safe_get(dados_conv, "empresa"))
                if dados_conv and safe_get(dados_conv, "empresa") in EMPRESAS_FATURAMENTO
                else 0
            )

            sistema = st.selectbox(
                "Sistema",
                SISTEMAS,
                index=SISTEMAS.index(safe_get(dados_conv, "sistema_utilizado"))
                if dados_conv and safe_get(dados_conv, "sistema_utilizado") in SISTEMAS
                else 0
            )

        # ---------------------- COLUNA 2 ----------------------
        with col2:
            site = st.text_input("Site/Portal", value=safe_get(dados_conv, "site"))
            login = st.text_input("Login", value=safe_get(dados_conv, "login"))
            senha = st.text_input("Senha", value=safe_get(dados_conv, "senha"))
            retorno = st.text_input("Prazo Retorno", value=safe_get(dados_conv, "prazo_retorno"))

        # ---------------------- COLUNA 3 ----------------------
        with col3:
            envio = st.text_input("Prazo Envio", value=safe_get(dados_conv, "envio"))
            validade = st.text_input("Validade da Guia", value=safe_get(dados_conv, "validade"))

            xml = st.radio(
                "Envia XML?",
                ["Sim", "Não"],
                index=0 if safe_get(dados_conv, "xml") != "Não" else 1
            )

            nf = st.radio(
                "Exige Nota Fiscal?",
                ["Sim", "Não"],
                index=0 if safe_get(dados_conv, "nf") != "Não" else 1
            )

        # --------------------------------------------------------
        # BLOCO XML + NF
        # --------------------------------------------------------
        colA, colB = st.columns(2)

        with colA:
            versao_xml = st.selectbox(
                "Versão XML (TISS)",
                VERSOES_TISS,
                index=VERSOES_TISS.index(safe_get(dados_conv, "versao_xml"))
                if dados_conv and safe_get(dados_conv, "versao_xml") in VERSOES_TISS
                else 0
            )

        with colB:
            fluxo_nf = st.selectbox(
                "Fluxo da Nota",
                ["Envia XML sem nota", "Envia NF junto com o lote"],
                index=0 if safe_get(dados_conv, "fluxo_nf") == "Envia XML sem nota" else 1
            )

        # --------------------------------------------------------
        # TEXTOS LONGOS
        # --------------------------------------------------------
        config_gerador = st.text_area("Configuração do Gerador XML", value=safe_get(dados_conv, "config_gerador"))
        doc_digitalizacao = st.text_area("Digitalização e Documentação", value=safe_get(dados_conv, "doc_digitalizacao"))
        observacoes = st.text_area("Observações Críticas", value=safe_get(dados_conv, "observacoes"))

        # --------------------------------------------------------
        # BOTÃO DE SALVAR
        # --------------------------------------------------------
        submit = st.form_submit_button("💾 Salvar Dados")

        if submit:

            # Dados consolidados
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
            
            if conv_id is None:
                novo_registro["id"] = generate_id(dados_atuais)
                dados_atuais.append(novo_registro)
            else:
                novo_registro["id"] = int(conv_id)
                # Localiza e atualiza o registro existente
                idx = next(i for i, c in enumerate(dados_atuais) if str(c["id"]) == str(conv_id))
                dados_atuais[idx] = novo_registro

            # Salva no GitHub uma única vez
            if github_save_file(dados_atuais, sha_atual):
                st.success(f"✔ Convênio {novo_registro['id']} salvo com sucesso!")
                time.sleep(0.5)
                st.rerun()

            # 🔥 Novo convênio → gera ID
            if conv_id is None:
                novo_registro["id"] = generate_id()
                dados_atuais.append(novo_registro)

            # 🔥 Atualização → mantém ID
            else:
                novo_registro["id"] = conv_id
                idx = next(i for i, c in enumerate(dados_atuais) if c["id"] == conv_id)
                dados_atuais[idx] = novo_registro

            # Salva no GitHub
            if github_save_file(dados_atuais, sha_atual):
                st.success("✔ Dados salvos com sucesso!")
                st.rerun()

    # --------------------------------------------------------
    # DOWNLOAD DO PDF
    # --------------------------------------------------------
    if dados_conv:
        st.download_button(
            "📥 Baixar PDF do Convênio",
            gerar_pdf(dados_conv),
            file_name=f"Manual_{safe_get(dados_conv, 'nome')}.pdf",
            mime="application/pdf"
        )


# ============================================================
# 10. PÁGINA — CONSULTA DE CONVÊNIOS
# ============================================================

def page_consulta(dados_atuais):

    if not dados_atuais:
        st.info("Nenhum convênio cadastrado.")
        return

    # Seleção segura por ID
    opcoes = sorted([f"{c['id']} — {safe_get(c, 'nome')}" for c in dados_atuais])
    escolha = st.selectbox("Selecione o convênio:", opcoes)

    conv_id = escolha.split(" — ")[0]
    dados = next(c for c in dados_atuais if c["id"] == conv_id)

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
    dados_atuais, sha_atual = github_get_file()

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
        page_cadastro(dados_atuais, sha_atual)

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


