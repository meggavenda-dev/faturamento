
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
    Layout idêntico ao modelo: barra azul de título, Seção 1 (duas colunas),
    Seção 2 (tabela 5 colunas) e 'OBSERVAÇÕES CRÍTICAS' com caixa multipágina.
    """

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(15, 12, 15)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # --- Paleta ---
    BLUE = (31, 73, 125)
    GREY_BAR = (230, 230, 230)
    TEXT = (0, 0, 0)
    CONTENT_W = pdf.w - pdf.l_margin - pdf.r_margin

    # --- Fontes ---
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

    # ---------- Helpers de layout ----------
    def bar_title(texto, top_margin=2, height=8):
        pdf.ln(top_margin)
        pdf.set_fill_color(*GREY_BAR)
        set_font(12, True)
        pdf.cell(0, height, f" {sanitize_text(texto).upper()}", ln=1, fill=True)
        pdf.ln(1)

    def label_value_heights(col_x, base_y, label, value, label_w, col_w, line_h=7, val_size=10):
        """
        Mede e desenha UMA linha de 'Label: Valor' (quebra valor em múltiplas linhas).
        Retorna a altura total usada. Garante que não ultrapasse a página.
        """
        label = sanitize_text(label)
        value = sanitize_text(value)
        usable = col_w - label_w

        # calcula linhas do valor
        set_font(val_size, False)
        lines = wrap_text(value, pdf, max(1, usable))
        needed_h = max(1, len(lines)) * line_h

        # quebra de página preventiva
        if base_y + needed_h > pdf.page_break_trigger:
            pdf.add_page()
            base_y = pdf.get_y()

        # desenha
        set_font(10, True)
        pdf.set_xy(col_x, base_y)
        pdf.cell(label_w, line_h, f"{label}:")
        set_font(val_size, False)

        pdf.set_xy(col_x + label_w, base_y)
        pdf.cell(usable, line_h, lines[0])
        for i in range(1, len(lines)):
            pdf.set_xy(col_x + label_w, base_y + i * line_h)
            pdf.cell(usable, line_h, lines[i])

        return needed_h

    def two_column_info(pares_esq, pares_dir, gap=10, label_w=28, line_h=7):
        col_w = (CONTENT_W - gap) / 2
        xL = pdf.l_margin
        xR = pdf.l_margin + col_w + gap
        y = pdf.get_y()

        max_rows = max(len(pares_esq), len(pares_dir))
        for i in range(max_rows):
            lblL, valL = pares_esq[i] if i < len(pares_esq) else ("", "")
            lblR, valR = pares_dir[i] if i < len(pares_dir) else ("", "")

            # mede cada lado (cada um pode pedir altura diferente)
            hL = label_value_heights(xL, y, lblL, valL, label_w, col_w, line_h=line_h)
            hR = label_value_heights(xR, y, lblR, valR, label_w, col_w, line_h=line_h)
            y = max(pdf.get_y(), y + max(hL, hR))

        pdf.set_y(y)  # cursor final

    def table(headers, rows, widths, header_h=8, cell_h=7):
        # Cabeçalho
        set_font(10, True)
        x0 = pdf.get_x()
        y0 = pdf.get_y()
        for i, head in enumerate(headers):
            pdf.set_xy(x0 + sum(widths[:i]), y0)
            pdf.cell(widths[i], header_h, sanitize_text(head), border=1, align="C")
        pdf.ln(header_h)

        # Linhas
        set_font(10, False)
        for row in rows:
            wrapped_cols = []
            max_lines = 1
            for i, val in enumerate(row):
                val = sanitize_text(val)
                lines = wrap_text(val, pdf, max(1, widths[i]-2))
                wrapped_cols.append(lines)
                max_lines = max(max_lines, len(lines))
            row_h = max_lines * cell_h

            # quebra de página com redesenho de cabeçalho
            if pdf.get_y() + row_h > pdf.page_break_trigger:
                pdf.add_page()
                set_font(10, True)
                xh = pdf.get_x()
                yh = pdf.get_y()
                for i, head in enumerate(headers):
                    pdf.set_xy(xh + sum(widths[:i]), yh)
                    pdf.cell(widths[i], header_h, sanitize_text(head), border=1, align="C")
                pdf.ln(header_h)
                set_font(10, False)

            x_row = pdf.get_x()
            y_row = pdf.get_y()
            for i, lines in enumerate(wrapped_cols):
                x_cell = x_row + sum(widths[:i])
                pdf.rect(x_cell, y_row, widths[i], row_h)
                for j, ln in enumerate(lines):
                    pdf.set_xy(x_cell + 1, y_row + j * cell_h)
                    pdf.cell(widths[i]-2, cell_h, ln)
            pdf.ln(row_h)

    def draw_multipage_box(text, left_margin, width, line_h=6.5, padding=1.5):
        """
        Desenha um bloco de texto com borda que pode ocupar várias páginas.
        Mantém as bordas corretamente em cada página.
        """
        text = sanitize_text(text or "")
        if text == "":
            # desenha uma caixa vazia com altura mínima
            y = pdf.get_y()
            min_h = line_h + 2 * padding
            if y + min_h > pdf.page_break_trigger:
                pdf.add_page()
                y = pdf.get_y()
            pdf.rect(left_margin, y, width, min_h)
            pdf.ln(min_h)
            return

        # Constrói linhas a partir da largura disponível (considerando padding)
        usable_w = width - 2 * padding
        set_font(10, False)
        lines = wrap_text(text, pdf, usable_w)

        # Fluxo de paginação
        i = 0
        while i < len(lines):
            y_top = pdf.get_y()
            # espaço útil na página (até o gatilho de quebra)
            space = pdf.page_break_trigger - y_top
            # altura disponível para conteúdo do box nesta página (tirando bordas/padding)
            # vamos reservar 2*padding + 1px extra para borda visual
            avail_h = max(0.0, space - 2 * padding - 0.5)

            # quantas linhas cabem nesta página?
            lines_per_page = int(avail_h // line_h) if avail_h > 0 else 0
            if lines_per_page <= 0:
                pdf.add_page()
                continue

            # fatia de linhas a renderizar nesta página
            end = min(len(lines), i + lines_per_page)
            slice_lines = lines[i:end]

            # altura real da caixa nesta página
            box_h = 2 * padding + len(slice_lines) * line_h

            # desenha borda da caixa
            pdf.rect(left_margin, y_top, width, box_h)

            # desenha as linhas com padding
            x_text = left_margin + padding
            y_text = y_top + padding
            for ln in slice_lines:
                pdf.set_xy(x_text, y_text)
                pdf.cell(usable_w, line_h, ln)
                y_text += line_h

            # atualiza ponteiros
            pdf.set_y(y_top + box_h)
            i = end

            # se ainda restam linhas, começamos nova página automaticamente
            if i < len(lines) and pdf.get_y() + line_h > pdf.page_break_trigger:
                pdf.add_page()

    # --------------------------
    # Título (barra azul)
    # --------------------------
    titulo_nome = sanitize_text(safe_get(dados, "nome")).upper()
    titulo_emp  = sanitize_text(safe_get(dados, "empresa")).upper()
    titulo_full = f"GUIA TÉCNICA: {titulo_nome}" + (f" - {titulo_emp}" if titulo_emp else "")

    pdf.set_fill_color(*BLUE)
    pdf.set_text_color(255, 255, 255)
    set_font(18, True)
    pdf.cell(0, 14, titulo_full, ln=1, align="C", fill=True)
    pdf.ln(2)
    pdf.set_text_color(*TEXT)

    # --------------------------
    # Seção 1
    # --------------------------
    bar_title("1. Dados de Identificação e Acesso")

    pares_esq = [
        ("Empresa", safe_get(dados, "empresa")),
        ("Portal",  safe_get(dados, "site")),
        ("Login",   safe_get(dados, "login")),
        ("Sistema", safe_get(dados, "sistema_utilizado")),
    ]
    pares_dir = [
        ("Código",  safe_get(dados, "codigo")),
        ("Senha",   safe_get(dados, "senha")),
        ("Retorno", safe_get(dados, "prazo_retorno")),
    ]
    two_column_info(pares_esq, pares_dir, gap=10, label_w=28, line_h=7)
    pdf.ln(2)

    # --------------------------
    # Seção 2 — Tabela
    # --------------------------
    bar_title("2. Cronograma e Regras Técnicas")

    w1 = 52
    w2 = 35
    w3 = 35
    w4 = 30
    w5 = CONTENT_W - (w1 + w2 + w3 + w4)
    widths = [w1, w2, w3, w4, w5]

    headers = ["Prazo Envio", "Validade Guia", "XML / Versão", "Nota Fiscal", "Fluxo NF"]

    xml_flag = safe_get(dados, "xml") or "—"
    xml_ver  = safe_get(dados, "versao_xml") or "—"
    xml_composto = f"{xml_flag} / {xml_ver}"

    row = [
        safe_get(dados, "envio"),
        safe_get(dados, "validade"),
        xml_composto,
        safe_get(dados, "nf"),
        safe_get(dados, "fluxo_nf"),
    ]
    table(headers, [row], widths, header_h=8, cell_h=7)
    pdf.ln(2)

    # --------------------------
    # Observações Críticas — multipágina
    # --------------------------
    bar_title("Observações Críticas")
    obs_text = safe_get(dados, "observacoes")
    draw_multipage_box(obs_text, left_margin=pdf.l_margin, width=CONTENT_W, line_h=6.5, padding=1.8)

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

