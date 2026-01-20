
# ============================================================
#  APP.PY — Manual de faturamento (Versão Completa)
# ============================================================

import streamlit as st
import requests
import base64
import json
import os
import pandas as pd
from fpdf import FPDF
import unicodedata
import re


# -----------------------------------------
#     CONFIGURAÇÕES DE ACESSO (SECRETS)
# -----------------------------------------
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_OWNER = st.secrets["REPO_OWNER"]
    REPO_NAME = st.secrets["REPO_NAME"]
except:
    st.error("Configure os Secrets (GITHUB_TOKEN, REPO_OWNER, REPO_NAME) no Streamlit Cloud.")
    st.stop()

FILE_PATH = "dados.json"
BRANCH = "main"

# -----------------------------------------
#     DESIGN — PALETA MICROSOFT/MV
# -----------------------------------------

PRIMARY_COLOR = "#1F497D"     # Azul Microsoft/MV
PRIMARY_LIGHT = "#E8EEF5"     # Azul clarinho
BG_LIGHT = "#F5F7FA"          # Fundo clean
GREY_BORDER = "#D9D9D9"
TEXT_DARK = "#2D2D2D"

# CSS GLOBAL
st.markdown(
    f"""
    <style>
        /* Ajuste da área de conteúdo para não colidir com o header fixo */
        .block-container {{
            padding-top: 5rem !important;
            max-width: 1200px;
        }}

        /* Header Fixo Ultra Elegante */
        .header-premium {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 70px;
            z-index: 9999;
            background: rgba(255, 255, 255, 0.8);
            backdrop-filter: blur(12px); /* Efeito de vidro */
            display: flex;
            align-items: center;
            padding: 0 40px;
            border-bottom: 1px solid {PRIMARY_COLOR}22;
            box-shadow: 0 2px 15px rgba(0,0,0,0.04);
        }}

        .header-title {{
            font-size: 24px;
            font-weight: 700;
            color: {PRIMARY_COLOR};
            letter-spacing: -0.5px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        /* Cards Estilo Microsoft (Bordas suaves e sombras leves) */
        .card {{
            background: #ffffff;
            padding: 24px;
            border-radius: 8px;
            border: 1px solid #e1e4e8;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.02);
            margin-bottom: 24px;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}

        .card:hover {{
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.05);
        }}

        /* Botões Estilo MV */
        .stButton>button {{
            background-color: {PRIMARY_COLOR} !important;
            color: white !important;
            border-radius: 4px !important;
            padding: 0.5rem 1.5rem !important;
            border: none !important;
            font-weight: 500 !important;
            font-size: 14px !important;
        }}
    </style>

    <div class="header-premium">
        <div class="header-title">
            <span>💼</span> Manual de Faturamento
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# -----------------------------------------
#     FUNÇÕES DO GITHUB – CRUD JSON
# -----------------------------------------
def buscar_dados_github():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}?ref={BRANCH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        content = response.json()
        decoded = base64.b64decode(content['content']).decode('utf-8')
        return json.loads(decoded), content['sha']
    else:
        return [], None


def sanitize_text(text):
    if text is None:
        return ""
    text = str(text)
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[\u200B-\u200F\u202A-\u202E\u2060-\u206F]", "", text)
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    return text.replace("\r", "")


def salvar_dados_github(novos_dados, sha):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    json_string = json.dumps(novos_dados, indent=4, ensure_ascii=False)
    encoded = base64.b64encode(json_string.encode('utf-8')).decode('utf-8')
    
    payload = {
        "message": "Update GABMA Database",
        "content": encoded,
        "branch": BRANCH
    }
    if sha:
        payload["sha"] = sha
    
    response = requests.put(url, headers=headers, json=payload)
    return response.status_code in [200, 201]


# ============================================================
#  PDF — GERADOR PREMIUM COM WRAP CORRIGIDO
# ============================================================

def gerar_pdf(dados):
    from fpdf import FPDF
    import os
    import unicodedata
    import re

    pdf = FPDF()
    pdf.set_margins(10, 10, 10)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # -----------------------------
    #  Fontes (UTF-8 se houver .ttf)
    # -----------------------------
    fonte_normal = "DejaVuSans.ttf"
    fonte_bold = "DejaVuSans-Bold.ttf"
    has_dejavu = os.path.exists(fonte_normal)
    has_dejavu_bold = os.path.exists(fonte_bold)

    if has_dejavu:
        pdf.add_font("DejaVu", "", fonte_normal, uni=True)
        if has_dejavu_bold:
            pdf.add_font("DejaVu", "B", fonte_bold, uni=True)
        font_family = "DejaVu"
    else:
        font_family = "Helvetica"

    def set_font(size, bold=False):
        style = ""
        if bold:
            # Se houver bold do DejaVu usa, se não usa bold nativo da Helvetica
            style = "B" if (font_family == "Helvetica" or has_dejavu_bold) else ""
        try:
            pdf.set_font(font_family, style, size)
        except:
            # fallback total
            pdf.set_font("Helvetica", "B" if bold else "", size)

    # -----------------------------
    #  Sanitização segura
    # -----------------------------
    def sanitize_text(text):
        if text is None:
            return ""
        t = str(text)
        # Normalização + remoções invisíveis/controle
        t = unicodedata.normalize("NFKD", t)
        t = re.sub(r"[\u200B-\u200F\u202A-\u202E\u2060-\u206F]", "", t)
        t = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", t)
        return t.replace("\r", "")

    # -----------------------------
    #  Helpers de layout
    # -----------------------------
    CONTENT_WIDTH = pdf.w - pdf.l_margin - pdf.r_margin

    def chunk_long_word(text, max_width):
        # Divide palavras gigantes (sem espaço)
        txt = sanitize_text(text or "")
        char_w = max(pdf.get_string_width("M"), 0.01)
        max_chars = max(int((max_width - 2) / char_w), 1)
        return [txt[i:i+max_chars] for i in range(0, len(txt), max_chars)] if txt else [""]

    def wrap_text(text, max_width):
        # Quebra respeitando espaços + fallback para palavras longas
        txt = sanitize_text(text or "")
        if not txt.strip():
            return [""]
        words = txt.split(" ")
        lines, current = [], ""
        for w in words:
            if pdf.get_string_width(w) > (max_width - 2):
                # fecha linha atual se houver
                if current:
                    lines.append(current)
                    current = ""
                lines.extend(chunk_long_word(w, max_width))
                continue
            candidate = (current + " " + w).strip() if current else w
            if pdf.get_string_width(candidate) <= (max_width - 2):
                current = candidate
            else:
                lines.append(current)
                current = w
        if current:
            lines.append(current)
        return lines

    def label_value_line(label, value, label_w=38, line_h=7):
        """
        Imprime 'Label: valor' em linha única com largura total CONTENT_WIDTH.
        O valor ocupa CONTENT_WIDTH - label_w.
        Sempre ancora X no início da área útil e restaura após imprimir.
        """
        x0, y0 = pdf.get_x(), pdf.get_y()
        pdf.set_x(pdf.l_margin)
        set_font(9, bold=True)
        pdf.cell(label_w, line_h, sanitize_text(f"{label}:"))
        set_font(9, bold=False)
        # valor como única linha (cell), com clip caso estoure (fica mais estável)
        usable_w = CONTENT_WIDTH - label_w
        # Se a string for maior que usable_w, fazemos wrap manual em seguida
        if pdf.get_string_width(sanitize_text(value)) <= (usable_w - 2):
            pdf.cell(usable_w, line_h, sanitize_text(value), ln=1)
        else:
            # quebra controlada
            lines = wrap_text(value, usable_w)
            # primeira linha
            pdf.cell(usable_w, line_h, lines[0], ln=1)
            # linhas seguintes, com a mesma indentação de label
            for i in range(1, len(lines)):
                pdf.set_x(pdf.l_margin + label_w)
                pdf.cell(usable_w, line_h, lines[i], ln=1)

        pdf.set_xy(pdf.l_margin, pdf.get_y())

    def two_cols_line(label_left, value_left, label_right, value_right, label_w=38, gap=8, line_h=7):
        """
        Linha 2 colunas: [Label: Valor] |gap| [Label: Valor]
        Evita colisão e respeita largura útil da página.
        """
        x_start = pdf.l_margin
        total_w = CONTENT_WIDTH
        col_w = (total_w - gap) / 2.0
        # Coluna esquerda
        pdf.set_x(x_start)
        set_font(9, bold=True)
        pdf.cell(label_w, line_h, sanitize_text(f"{label_left}:"))
        set_font(9, bold=False)
        left_usable = col_w - label_w
        left_text = sanitize_text(value_left)
        # impressões em altura calculada
        left_lines = wrap_text(left_text, left_usable)
        left_h = max(1, len(left_lines)) * line_h

        # Coluna direita (medição)
        set_font(9, bold=True)
        right_label_w = label_w
        right_usable = col_w - right_label_w
        right_text = sanitize_text(value_right)
        right_lines = wrap_text(right_text, right_usable)
        right_h = max(1, len(right_lines)) * line_h

        row_h = max(left_h, right_h)

        # Page break se necessário
        if pdf.get_y() + row_h > pdf.page_break_trigger:
            pdf.add_page()

        # Render coluna esquerda
        set_font(9, bold=True)
        pdf.set_xy(x_start, pdf.get_y())
        pdf.cell(label_w, line_h, sanitize_text(f"{label_left}:"))
        set_font(9, bold=False)
        x_left_text = pdf.get_x()
        y_left_text = pdf.get_y()
        for i, ln in enumerate(left_lines):
            pdf.set_xy(x_left_text, y_left_text + i * line_h)
            pdf.cell(left_usable, line_h, ln)

        # Render coluna direita
        x_right = x_start + col_w + gap
        set_font(9, bold=True)
        pdf.set_xy(x_right, y_left_text)
        pdf.cell(right_label_w, line_h, sanitize_text(f"{label_right}:"))
        set_font(9, bold=False)
        x_right_text = pdf.get_x()
        for i, ln in enumerate(right_lines):
            pdf.set_xy(x_right_text, y_left_text + i * line_h)
            pdf.cell(right_usable, line_h, ln)

        # Avança Y
        pdf.set_xy(pdf.l_margin, y_left_text + row_h)

    def draw_row(col_widths, data, aligns=None, line_h=6, pad=1):
        """
        Tabela com altura uniforme e quebra por coluna.
        """
        aligns = aligns or ["L"] * len(col_widths)
        col_lines = [wrap_text(t, col_widths[i] - pad * 2) for i, t in enumerate(data)]
        max_lines = max(len(c) for c in col_lines) if col_lines else 1
        row_h = max_lines * line_h

        if pdf.get_y() + row_h > pdf.page_break_trigger:
            pdf.add_page()

        x0, y0 = pdf.get_x(), pdf.get_y()
        for i, w in enumerate(col_widths):
            x = pdf.get_x()
            y = pdf.get_y()
            pdf.rect(x, y, w, row_h)
            for j, line in enumerate(col_lines[i]):
                pdf.set_xy(x + pad, y + j * line_h)
                pdf.cell(w - pad * 2, line_h, line, border=0, ln=0, align=aligns[i])
            pdf.set_xy(x + w, y)
        pdf.set_xy(x0, y0 + row_h)

    # -----------------------------
    #  Cabeçalho
    # -----------------------------
    pdf.set_fill_color(31, 73, 125)
    pdf.set_text_color(255, 255, 255)
    set_font(16, bold=True)
    pdf.cell(0, 15, sanitize_text(f"GUIA TÉCNICA: {str(dados.get('nome','')).upper()}"), ln=True, align='C', fill=True)
    pdf.ln(5)

    # -----------------------------
    #  Seção 1 – Identificação e Acesso (ancorada)
    # -----------------------------
    pdf.set_text_color(0, 0, 0)
    pdf.set_fill_color(230, 230, 230)
    set_font(11, bold=True)
    pdf.cell(0, 8, " 1. DADOS DE IDENTIFICAÇÃO E ACESSO", ln=True, fill=True)
    pdf.ln(2)

    # Linha 1: Empresa | Código
    two_cols_line("Empresa", dados.get("empresa", "N/A"),
                  "Código", dados.get("codigo", "N/A"))

    # Linha 2: Portal (quebra controlada, ocupando largura total)
    label_value_line("Portal", dados.get("site", "") or "—")

    # Linha 3: Login | Senha
    two_cols_line("Login", dados.get("login", ""),
                  "Senha", dados.get("senha", ""))

    # Linha 4: Sistema | Retorno
    two_cols_line("Sistema", dados.get("sistema_utilizado", "N/A"),
                  "Retorno", dados.get("prazo_retorno", "N/A"))

    pdf.ln(4)

    # -----------------------------
    #  Seção 2 – Tabela TISS
    # -----------------------------
    pdf.set_fill_color(230, 230, 230)
    set_font(11, bold=True)
    pdf.cell(0, 8, " 2. CRONOGRAMA E REGRAS TÉCNICAS", ln=True, fill=True)
    pdf.ln(2)

    set_font(8, bold=True)
    col_w = [45, 30, 25, 25, 65]
    aligns = ['C', 'C', 'C', 'C', 'C']
    draw_row(col_w, ["Prazo Envio", "Validade Guia", "XML / Versão", "Nota Fiscal", "Fluxo NF"], aligns=aligns, line_h=7)

    set_font(8, bold=False)
    # Observação: "XML / Versão" usa 'xml' (Sim/Não) + 'versao_xml'
    xml_flag = dados.get("xml", "")
    xml_ver = dados.get("versao_xml", "-")
    draw_row(
        col_w,
        [
            sanitize_text(dados.get("envio", "")),
            f"{str(dados.get('validade', ''))} dias" if str(dados.get('validade', '')).strip() else "—",
            f"{xml_flag} / {xml_ver}",
            str(dados.get("nf", "")),
            str(dados.get("fluxo_nf", "N/A"))
        ],
        aligns=aligns,
        line_h=7
    )
    pdf.ln(5)

    # -----------------------------
    #  Seção 3 – Blocos
    # -----------------------------
    def bloco(titulo, conteudo):
        txt = sanitize_text(conteudo or "").strip()
        if not txt:
            return
        set_font(11, bold=True)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(0, 7, f" {titulo}", ln=True, fill=True)
        set_font(9, bold=False)
        pdf.multi_cell(0, 5, txt, border=1)
        pdf.ln(3)

    bloco("CONFIGURAÇÃO DO GERADOR XML", dados.get("config_gerador", ""))
    bloco("DIGITALIZAÇÃO E DOCUMENTAÇÃO", dados.get("doc_digitalizacao", ""))
    bloco("OBSERVAÇÕES CRÍTICAS", dados.get("observacoes", ""))

    # -----------------------------
    #  Rodapé
    # -----------------------------
    pdf.set_y(-20)
    pdf.set_text_color(120, 120, 120)
    set_font(8, bold=False)
    pdf.cell(0, 10, "Manual de faturamento", align='C')

    return bytes(pdf.output())

# ============================================================
#       APP – INÍCIO
# ============================================================
st.set_page_config(page_title="GABMA – Sistema Técnico", layout="wide")

st.markdown(f"<div class='main-title'>💼 Manual de faturamento</div>", unsafe_allow_html=True)

dados_atuais, sha_atual = buscar_dados_github()

# MENU
menu = st.sidebar.radio(
    "Navegação",
    ["Cadastrar / Editar", "Consulta de Convênios", "Visualizar Banco"]
)


# ============================================================
#           CADASTRO & EDIÇÃO
# ============================================================
if menu == "Cadastrar / Editar":

    st.markdown("<div class='card'><div class='card-title'>📝 Cadastro de Convênio</div>", unsafe_allow_html=True)

    nomes = ["+ Novo Convênio"] + sorted([c["nome"] for c in dados_atuais])
    escolha = st.selectbox("Selecione um convênio:", nomes)

    dados_conv = next((c for c in dados_atuais if c["nome"] == escolha), None)

    VERSOES_TISS = ["4.03.00", "4.02.00", "4.01.00", "01.06.00", "3.05.00", "3.04.01"]

    with st.form("form_cadastro"):
        col1, col2, col3 = st.columns(3)

        # Coluna 1
        with col1:
            nome = st.text_input("Nome do Convênio", value=dados_conv["nome"] if dados_conv else "")
            codigo = st.text_input("Código", value=dados_conv.get("codigo", "") if dados_conv else "")
            empresa = st.text_input("Empresa Faturamento", value=dados_conv.get("empresa", "") if dados_conv else "")
            sistema = st.selectbox("Sistema", ["Orizon", "Benner", "Maida", "Facil", "Visual TISS", "Próprio"])

        # Coluna 2
        with col2:
            site = st.text_input("Site/Portal", value=dados_conv["site"] if dados_conv else "")
            login = st.text_input("Login", value=dados_conv["login"] if dados_conv else "")
            senha = st.text_input("Senha", value=dados_conv["senha"] if dados_conv else "")
            retorno = st.text_input("Prazo Retorno", value=dados_conv.get("prazo_retorno", "") if dados_conv else "")

        # Coluna 3
        with col3:
            envio = st.text_input("Prazo Envio", value=dados_conv["envio"] if dados_conv else "")
            validade = st.text_input("Validade Guia", value=dados_conv["validade"] if dados_conv else "")
            xml = st.radio("Envia XML?", ["Sim", "Não"], index=0 if not dados_conv or dados_conv["xml"] == "Sim" else 1)
            nf = st.radio("Exige NF?", ["Sim", "Não"], index=0 if not dados_conv or dados_conv["nf"] == "Sim" else 1)

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        col_a, col_b = st.columns(2)

        v_xml = col_a.selectbox(
            "Versão XML (Padrão TISS)",
            VERSOES_TISS,
            index=(VERSOES_TISS.index(dados_conv.get("versao_xml"))
                if dados_conv and dados_conv.get("versao_xml") in VERSOES_TISS else 0)
        )

        fluxo_nf = col_b.selectbox(
            "Fluxo Nota",
            ["Envia XML sem nota", "Envia NF junto com o lote"]
        )

        config_gerador = st.text_area("Configuração Gerador XML", value=dados_conv.get("config_gerador", "") if dados_conv else "")
        doc_dig = st.text_area("Digitalização e Documentação", value=dados_conv.get("doc_digitalizacao", "") if dados_conv else "")
        obs = st.text_area("Observações Críticas", value=dados_conv["observacoes"] if dados_conv else "")

        if st.form_submit_button("💾 Salvar Dados"):
            novo = {
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
                "nf": nf,
                "fluxo_nf": fluxo_nf,
                "xml": xml,
                "versao_xml": v_xml,
                "config_gerador": config_gerador,
                "doc_digitalizacao": doc_dig,
                "observacoes": obs
            }

            if escolha == "+ Novo Convênio":
                dados_atuais.append(novo)
            else:
                idx = next(i for i, c in enumerate(dados_atuais) if c["nome"] == escolha)
                dados_atuais[idx] = novo

            if salvar_dados_github(dados_atuais, sha_atual):
                st.success("Dados salvos com sucesso!")
                st.rerun()

    if dados_conv:
        st.download_button(
            "📥 Baixar PDF do Convênio",
            gerar_pdf(dados_conv),
            f"GABMA_{escolha}.pdf",
            "application/pdf"
        )


# ============================================================
#       CONSULTA DE CONVÊNIOS
# ============================================================
elif menu == "Consulta de Convênios":

    st.markdown("<div class='card'><div class='card-title'>🔎 Consulta de Convênios</div>", unsafe_allow_html=True)

    if not dados_atuais:
        st.info("Nenhum convênio cadastrado.")
        st.stop()

    nomes_conv = sorted([c["nome"] for c in dados_atuais])
    escolha = st.selectbox("Selecione o convênio:", nomes_conv)

    dados = next(c for c in dados_atuais if c["nome"] == escolha)

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
            {dados["nome"].upper()}
        </div>
        """,
        unsafe_allow_html=True
    )

    # Identificação
    st.markdown("<div class='card'><div class='card-title'>🧾 Dados de Identificação</div>", unsafe_allow_html=True)
    st.markdown(f"""
        <div class='info-line'>Empresa: <span class='value'>{dados.get('empresa','N/A')}</span></div>
        <div class='info-line'>Código: <span class='value'>{dados.get('codigo','N/A')}</span></div>
        <div class='info-line'>Sistema: <span class='value'>{dados.get('sistema_utilizado','N/A')}</span></div>
        <div class='info-line'>Retorno: <span class='value'>{dados.get('prazo_retorno','N/A')}</span></div>
    """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Acesso
    st.markdown("<div class='card'><div class='card-title'>🔐 Acesso ao Portal</div>", unsafe_allow_html=True)
    st.markdown(f"""
        <div class='info-line'>Portal: <span class='value'>{dados['site']}</span></div>
        <div class='info-line'>Login: <span class='value'>{dados['login']}</span></div>
        <div class='info-line'>Senha: <span class='value'>{dados['senha']}</span></div>
    """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Técnicos
    st.markdown("<div class='card'><div class='card-title'>📦 Regras Técnicas</div>", unsafe_allow_html=True)
    st.markdown(f"""
        <div class='info-line'>Prazo Envio: <span class='value'>{dados['envio']}</span></div>
        <div class='info-line'>Validade Guia: <span class='value'>{dados['validade']} dias</span></div>
        <div class='info-line'>Envia XML? <span class='value'>{dados['xml']}</span></div>
        <div class='info-line'>Versão XML: <span class='value'>{dados.get('versao_xml','N/A')}</span></div>
        <div class='info-line'>Exige NF? <span class='value'>{dados['nf']}</span></div>
        <div class='info-line'>Fluxo da Nota: <span class='value'>{dados.get('fluxo_nf','N/A')}</span></div>
    """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Blocos extras
    if dados.get("config_gerador"):
        st.markdown("<div class='card'><div class='card-title'>⚙️ Configuração XML</div>", unsafe_allow_html=True)
        st.code(dados["config_gerador"])
        st.markdown("</div>", unsafe_allow_html=True)

    if dados.get("doc_digitalizacao"):
        st.markdown("<div class='card'><div class='card-title'>🗂 Digitalização e Documentação</div>", unsafe_allow_html=True)
        st.info(dados["doc_digitalizacao"])
        st.markdown("</div>", unsafe_allow_html=True)

    if dados.get("observacoes"):
        # Unificamos a abertura do card, o título e o conteúdo em um único markdown
        conteudo_obs = dados["observacoes"].replace("\n", "<br>") # Preserva quebras de linha
        
        st.markdown(
            f"""
            <div class='card'>
                <div class='card-title'>⚠️ Observações Críticas</div>
                <div style="
                    background-color: white;
                    color: {TEXT_DARK};
                    border-left: 4px solid {PRIMARY_COLOR};
                    padding: 12px 16px;
                    border-radius: 6px;
                    font-size: 15px;
                    line-height: 1.5;">
                    {conteudo_obs}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.caption("Manual de Faturamento — Visualização Premium")


# ============================================================
#       VISUALIZAR BANCO
# ============================================================
elif menu == "Visualizar Banco":

    st.markdown("<div class='card'><div class='card-title'>📋 Banco de Dados Completo</div>", unsafe_allow_html=True)

    if dados_atuais:
        st.dataframe(pd.DataFrame(dados_atuais))
    else:
        st.info("Banco vazio.")

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
#  DESIGN FLUENT 2 + HEADER FIXO
# ============================================================
st.markdown(
    f"""
    <style>
        .card {{
            transition: all 0.18s ease-in-out;
        }}
        .card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }}

        .header-premium {{
            position: sticky;
            top: 0;
            z-index: 999;
            background: white;
            padding: 18px 10px;
            border-bottom: 2px solid {PRIMARY_COLOR}22;
            backdrop-filter: blur(4px);
        }}

        .header-title {{
            font-size: 30px;
            font-weight: 700;
            color: {PRIMARY_COLOR};
        }}

        .stButton>button {{
            background-color: {PRIMARY_COLOR};
            color: white;
            border-radius: 6px;
            padding: 8px 16px;
            border: none;
            font-weight: 600;
            transition: 0.2s;
        }}
        .stButton>button:hover {{
            background-color: #16375E;
        }}

        .block-container {{
            padding-top: 0px !important;
        }}
    </style>
    """,
    unsafe_allow_html=True
)

# HEADER FIXO
st.markdown(
    f"""
    <div class="header-premium">
        <span class="header-title">💼 Manual de faturamento</span>
    </div>
    """,
    unsafe_allow_html=True
)
st.write("")

# Sidebar Refresh
st.sidebar.markdown("### 🔄 Atualização")
if st.sidebar.button("Recarregar Sistema"):
    st.rerun()

# Footer
st.markdown(
    f"""
    <br><br>
    <div style='text-align:center; color:#777; font-size:13px; padding:10px;'>
        © 2026 — Manual de faturamento<br>
        Desenvolvido com design corporativo Microsoft/MV
    </div>
    """,
    unsafe_allow_html=True
)
