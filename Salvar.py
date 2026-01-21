
# ============================================================
#  APP.PY — MANUAL DE FATURAMENTO (VERSÃO PREMIUM)
#  COLUNA ÚNICA NA SEÇÃO 1 • TABELA DA SEÇÃO 2 IGUAL AO PRINT
#  OBSERVAÇÕES CRÍTICAS COM PARÁGRAFOS + BULLETS E ESPAÇOS CORRIGIDOS
#  PDF UNICODE (DejaVu) + WRAP DE URL SEM ESPAÇOS EXTRAS
#  TÍTULO: SOMENTE NOME DO CONVÊNIO
# ============================================================

# ------------------------------------------------------------
# 1. IMPORTS
# ------------------------------------------------------------
import os
import re
import json
import time
import base64
import random
import unicodedata

import requests
import pandas as pd
from fpdf import FPDF
import streamlit as st

# ------------------------------------------------------------
# 2. GITHUB DATABASE (Incluído no módulo — sem import externo)
#    Seguro | Atômico | Anti-race | SHA locking | Cache curto
# ------------------------------------------------------------
class GitHubJSON:
    API_URL = "https://api.github.com/repos/{owner}/{repo}/contents/{path}"

    def __init__(self, token, owner, repo, path="dados.json", branch="main"):
        self.token = token
        self.owner = owner
        self.repo = repo
        self.path = path
        self.branch = branch

        # Cache ultra-curto para evitar GET múltiplos desnecessários
        self._cache_data = None
        self._cache_sha = None
        self._cache_time = 0.0

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }

    # ============================
    # LOAD — Leitura segura (200ms)
    # ============================
    def load(self, force=False):
        now = time.time()
        if not force and self._cache_data is not None:
            if (now - self._cache_time) < 0.2:  # cache curtíssimo
                return self._cache_data, self._cache_sha

        url = self.API_URL.format(owner=self.owner, repo=self.repo, path=self.path)
        r = requests.get(url, headers=self.headers, params={"ref": self.branch})

        if r.status_code == 404:
            # Arquivo não existe — retorna base vazia
            self._cache_data = []
            self._cache_sha = None
            self._cache_time = now
            return [], None

        if r.status_code != 200:
            raise Exception(f"GitHub GET error: {r.status_code} - {r.text}")

        body = r.json()
        sha = body.get("sha")

        decoded = base64.b64decode(body["content"]).decode("utf-8")
        data = json.loads(decoded)

        self._cache_data = data
        self._cache_sha = sha
        self._cache_time = now

        return data, sha

    # ============================================
    # SAVE — Salvamento atômico com SHA locking
    # ============================================
    def save(self, new_data, retries=8):
        for attempt in range(retries):
            # SHA sempre atualizado
            _, sha = self.load(force=True)

            url = self.API_URL.format(owner=self.owner, repo=self.repo, path=self.path)
            encoded = base64.b64encode(
                json.dumps(new_data, indent=4, ensure_ascii=False).encode("utf-8")
            ).decode("utf-8")

            payload = {
                "message": "Atualização Manual Faturamento",
                "content": encoded,
                "sha": sha,
                "branch": self.branch,
            }

            r = requests.put(url, headers=self.headers, json=payload)

            # SALVO COM SUCESSO
            if r.status_code in (200, 201):
                body = r.json()
                new_sha = body["content"]["sha"]

                # Atualiza cache
                self._cache_data = new_data
                self._cache_sha = new_sha
                self._cache_time = time.time()
                return True

            # SHA inválido => arquivo mudou no GitHub => retry exponencial
            if r.status_code == 409:
                time.sleep((2 ** attempt) * 0.15 + random.random() * 0.2)
                continue

            # Rate limit
            if r.status_code == 403 and "rate" in r.text.lower():
                time.sleep(2 + random.random())
                continue

            raise Exception(f"GitHub PUT error: {r.status_code} - {r.text}")

        raise TimeoutError("Falha ao salvar após múltiplas tentativas.")

    # =================================================
    # UPDATE — Carregar, alterar e salvar com atomicidade
    # =================================================
    def update(self, update_fn):
        for attempt in range(8):
            data, _ = self.load(force=True)
            new_data = update_fn(data)

            try:
                self.save(new_data)
                return True
            except TimeoutError:
                continue
            except Exception:
                time.sleep(0.2)

        raise Exception("Falha ao atualizar após múltiplas tentativas.")

# ------------------------------------------------------------
# 3. CONFIGURAÇÃO DE ACESSO (SECRETS)
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
# 4. CONSTANTES / PALETA
# ------------------------------------------------------------
PRIMARY_COLOR = "#1F497D"
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

OPCOES_XML = ["Sim", "Não"]
OPCOES_NF = ["Sim", "Não"]
OPCOES_FLUXO_NF = ["Envia XML sem nota", "Envia NF junto com o lote"]

# ------------------------------------------------------------
# 5. CSS GLOBAL + HEADER FIXO (injetado no main)
# ------------------------------------------------------------
CSS_GLOBAL = f"""
<style>
  .block-container {{
      padding-top: 6rem !important;
      max-width: 1200px !important;
  }}
  .header-premium {{
      position: fixed; top: 0; left: 0;
      width: 100%; height: 70px;
      background: rgba(255,255,255,0.85);
      backdrop-filter: blur(10px);
      border-bottom: 1px solid {PRIMARY_COLOR}33;
      display: flex; align-items: center;
      padding: 0 40px; z-index: 999;
      box-shadow: 0 4px 10px rgba(0,0,0,0.05);
  }}
  .header-title {{
      font-size: 24px; font-weight: 700;
      color: {PRIMARY_COLOR};
      letter-spacing: -0.5px;
      display: flex; align-items: center; gap: 10px;
  }}
  .card {{
      background: #ffffff;
      padding: 24px;
      border-radius: 8px;
      border: 1px solid #e1e4e8;
      box-shadow: 0 4px 6px rgba(0,0,0,0.03);
      margin-bottom: 24px;
  }}
  .card-title {{
      font-size: 20px;
      font-weight: 700;
      margin-bottom: 15px;
      color: {PRIMARY_COLOR};
  }}
  .stButton > button {{
      background-color: {PRIMARY_COLOR} !important;
      color: white !important;
      border-radius: 6px !important;
      padding: 8px 18px !important;
      font-weight: 600 !important;
      border: none !important;
  }}
  .stButton > button:hover {{ background-color: #16375E !important; }}
</style>
<div class="header-premium">
    <span class="header-title">💼 Manual de Faturamento</span>
</div>
"""

# ============================================================
# 6. UTILITÁRIAS — Unicode + correção forte de espaços
# ============================================================
def ui_text(value):
    if not value:
        return ""
    return sanitize_text(value)   




def fix_technical_spacing(txt: str) -> str:
    if not txt:
        return ""

    urls = {}
    def _url_replacer(match):
        key = f"\u0000{len(urls)}\u0000"
        urls[key] = match.group(0)
        return key

    # 1) Protege URLs para não inserir espaços no meio delas
    txt = re.sub(r"https?://[^\s<>\"']+", _url_replacer, txt)

    # 2) Espaço entre Números e Letras (ex: 90dias -> 90 dias)
    txt = re.sub(r"(\d)([A-Za-zÁÉÍÓÚÂÊÔÃÕÀÇáéíóúâêôãõàç])", r"\1 \2", txt)
    txt = re.sub(r"([A-Za-zÁÉÍÓÚÂÊÔÃÕÀÇáéíóúâêôãõàç])(\d)", r"\1 \2", txt)

    # 3) Espaço após pontuação se estiver colado (ex: fechar.> -> fechar. >)
    # Ignora pontos decimais em números
    txt = re.sub(r"(?<!\d)\.(?=[^\s\d])", ". ", txt)
    txt = re.sub(r":(?!\s)", ": ", txt)
    txt = re.sub(r";(?!\s)", "; ", txt)

    # 4) Espaços ao redor de operadores e delimitadores técnicos
    txt = re.sub(r"\s*>\s*", " > ", txt)
    txt = re.sub(r"\s*/\s*", " / ", txt)
    
    # 5) Correções específicas de colagem comuns em faturamento
    correcoes = {
        r"PELASMARTKIDS": "PELA SMARTKIDS",
        r"serpediatria": "ser pediatria",
        r"depacote": "de pacote",
        r"diasútil": "dias útil",
        r"às12:00": "às 12:00",
        r"sófechar": "só fechar",
        r"gera oXML": "gera o XML",
        r"noSisAmil": "no SisAmil"
    }
    for erro, certo in correcoes.items():
        txt = re.sub(erro, certo, txt, flags=re.IGNORECASE)

    # 6) Bullets coladas (•Texto -> • Texto)
    txt = re.sub(r"([•\-–—\*→])([^\s])", r"\1 \2", txt)

    # 7) Restaura URLs
    for k, v in urls.items():
        txt = txt.replace(k, v)

    return txt


def sanitize_text(text: str) -> str:
    if not text:
        return ""
    txt = str(text)
    # Normalização e remoção de caracteres invisíveis que causam colagem
    txt = unicodedata.normalize("NFKC", txt)
    txt = re.sub(r"[\u00A0\u200B-\u200F\uFEFF]", " ", txt) 
    
    # Aplica correções de espaçamento
    txt = fix_technical_spacing(txt)
    
    # Remove espaços duplos
    txt = re.sub(r"[ \t]+", " ", txt)
    return txt.strip()

    
def normalize(value):
    if not value: return ""
    return sanitize_text(value).strip().lower()

def generate_id(dados_atuais):
    ids = []
    for item in dados_atuais:
        try:
            id_val = int(item.get("id"))
            if id_val > 0: ids.append(id_val)
        except Exception: continue
    return max(ids) + 1 if ids else 1

def safe_get(data, key, default=""):
    if not isinstance(data, dict):
        return default
    return data.get(key, default) or ""

# ============================================================
# 7. WRAP DE TEXTO (URLs, palavras longas) + utilidades
# ============================================================
def chunk_text(text, size):
    safe_size = int(size) if size and size >= 1 else 1
    return [text[i:i+safe_size] for i in range(0, len(text), safe_size)]

def _split_token_preserving_delims(token: str):
    """
    Para tokens tipo URL/caminho, quebra por delimitadores mantendo-os
    NO FIM do segmento (sem inserir espaços).
    Ex.: 'https://a/b?x=1' -> ['https://a/', 'b?', 'x=', '1']
    """
    parts = re.split(r"([/?&=._-])", token)
    segs = []
    i = 0
    while i < len(parts):
        seg = parts[i]
        if seg == "":
            i += 1
            continue
        if i + 1 < len(parts) and re.fullmatch(r"[/?&=._-]", parts[i+1] or ""):
            seg += parts[i+1]
            i += 2
        else:
            i += 1
        segs.append(seg)
    return segs

def wrap_text(text, pdf, max_width):
    if not text:
        return [""]

    # Divide por espaços preservando a intenção original
    words = text.split(" ")
    lines, current = [], ""

    def width(s): return pdf.get_string_width(s)

    for w in words:
        if not w: continue
        
        # Se for uma URL ou texto com delimitadores, usamos a lógica de quebra por caractere
        if any(ch in w for ch in "/?&=._-") and width(w) > max_width:
            segments = _split_token_preserving_delims(w)
            for seg in segments:
                candidate = current + seg
                if width(candidate) <= max_width:
                    current = candidate
                else:
                    if current: lines.append(current)
                    current = seg
            continue

        # Palavra normal
        candidate = f"{current} {w}".strip() if current else w
        if width(candidate) <= max_width:
            current = candidate
        else:
            if current: lines.append(current)
            current = w

    if current:
        lines.append(current)
    return lines

# ============================================================
# 8. PDF — fontes e OBSERVAÇÕES (parágrafos + bullets + correções de espaço)
# ============================================================
def _pdf_set_fonts(pdf: FPDF) -> str:
    """
    Tenta usar DejaVu (Unicode). Se não achar, cai em Helvetica.
    Compatível com FPDF 1.x e fpdf2.
    """
    fonte_normal = "DejaVuSans.ttf"
    fonte_bold = "DejaVuSans-Bold.ttf"
    has_normal = os.path.exists(fonte_normal)
    has_bold = os.path.exists(fonte_bold)

    if has_normal:
        try:
            pdf.add_font("DejaVu", "", fonte_normal, uni=True)
            if has_bold:
                pdf.add_font("DejaVu", "B", fonte_bold, uni=True)
            return "DejaVu"
        except Exception:
            pass
    return "Helvetica"


def build_wrapped_lines(text, pdf, usable_w, line_h, bullet_indent=4.0):
    lines_out = []
    if not text: return []

    text = sanitize_text(text)  # ✅ UMA ÚNICA VEZ

    paragraphs = text.split('\n')
    bullet_re = re.compile(r"^\s*(?:[\u2022•\-–—\*]|->|→)\s*(.*)$")
    
    for p in paragraphs:
        p = p.strip()
        if not p:
            lines_out.append(("", 0.0))
            continue
    
        m = bullet_re.match(p)
        if m:
            content = m.group(1).strip()
            wrapped = wrap_text("• " + content, pdf, usable_w - bullet_indent)
            for wline in wrapped:
                lines_out.append((wline, bullet_indent))
        else:
            wrapped = wrap_text(p, pdf, usable_w)
            for wline in wrapped:
                lines_out.append((wline, 0.0))
    return lines_out
    
# ============================================================
# 9. GERAÇÃO DO PDF — layout completo
# ============================================================
def gerar_pdf(dados):
    """
    Layout: título azul,
    Seção 1 (COLUNA ÚNICA),
    Seção 2 (tabela 5 colunas idêntica ao print),
    e 'Observações Críticas' multipágina.
    """
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(15, 12, 15)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    BLUE = (31, 73, 125)
    GREY_BAR = (230, 230, 230)   # barra de seção
    TEXT = (0, 0, 0)
    CONTENT_W = pdf.w - pdf.l_margin - pdf.r_margin

    FONT = _pdf_set_fonts(pdf)
    def set_font(size=10, bold=False):
        style = "B" if bold else ""
        try:
            pdf.set_font(FONT, style, size)
        except Exception:
            pdf.set_font("Helvetica", style, size)

    # ---------- Helpers ----------
    def bar_title(texto, top_margin=3, height=8):
        pdf.ln(top_margin)
        pdf.set_fill_color(*GREY_BAR)
        set_font(12, True)
        pdf.cell(0, height, f" {texto.upper()}", ln=1, fill=True)
        pdf.ln(1.5)

    # === COLUNA ÚNICA: label à esquerda (largura fixa) + valor à direita (wrap) ===
    def one_column_info(pares, label_w=30, line_h=6.8, gap_y=1.6, val_size=10):
        """
        Desenha pares ("Label", "Valor") em UMA coluna:
        - label com largura fixa (label_w)
        - valor ocupa (CONTENT_W - label_w)
        - respeita quebra de página e quebra de linha (wrap_text)
        """
        x = pdf.l_margin
        y = pdf.get_y()
        col_w = CONTENT_W
        usable_w = col_w - label_w

        for (label, value) in pares:
            label = label or ""
            value = value or ""

            # mede linhas do valor
            set_font(val_size, False)
            value = sanitize_text(value)
            lines = wrap_text(value, pdf, max(1, usable_w))
            needed_h = max(1, len(lines)) * line_h

            # quebra de página preventiva
            if y + needed_h > pdf.page_break_trigger:
                pdf.add_page()
                y = pdf.get_y()

            # desenha label
            set_font(10, True)
            pdf.set_xy(x, y)
            pdf.cell(label_w, line_h, f"{label}:")

            # desenha primeira linha do valor
            set_font(val_size, False)
            pdf.set_xy(x + label_w, y)
            pdf.cell(usable_w, line_h, lines[0] if lines else "")

            # linhas seguintes (se houver)
            for i in range(1, len(lines)):
                pdf.set_xy(x + label_w, y + i * line_h)
                pdf.cell(usable_w, line_h, lines[i])

            # avança Y
            y = y + needed_h + gap_y

        pdf.set_y(y)

    # --------------------------
    # Título (barra azul) — SOMENTE NOME DO CONVÊNIO
    # --------------------------
    nome_conv = sanitize_text(safe_get(dados, "nome")).upper()
    titulo_full = f"MANUAL: {nome_conv}" if nome_conv else "GUIA TÉCNICA"

    pdf.set_fill_color(*BLUE)
    pdf.set_text_color(255, 255, 255)
    set_font(18, True)
    pdf.cell(0, 14, titulo_full, ln=1, align="C", fill=True)
    pdf.set_text_color(*TEXT)
    pdf.ln(5)

    # --------------------------
    # Seção 1 — COLUNA ÚNICA
    # --------------------------
    bar_title("1. Dados de Identificação e Acesso")

    pares_unicos = [
        ("Empresa",  safe_get(dados, "empresa")),
        ("Código",   safe_get(dados, "codigo")),
        ("Portal",   safe_get(dados, "site")),
        ("Senha",    safe_get(dados, "senha")),
        ("Login",    safe_get(dados, "login")),
        ("Retorno",  safe_get(dados, "prazo_retorno")),
        ("Sistema",  safe_get(dados, "sistema_utilizado")),
    ]
    one_column_info(pares_unicos, label_w=30, line_h=6.8, gap_y=1.6, val_size=10)
    pdf.ln(2.0)

    # --------------------------
    # Tabela "2. CRONOGRAMA..." (igual ao print)
    # --------------------------
    def table(headers, rows, widths, header_h=8.0, cell_h=6.0, pad=2.0):
        """
        Tabela com:
        - Cabeçalho cinza claro, textos centralizados
        - Corpo com padding interno (pad) e quebra suave por coluna
        - Bordas padrão, redesenha cabeçalho ao quebrar página
        """
        # Cabeçalho
        set_font(10, True)
        pdf.set_fill_color(242, 242, 242)   # cinza claro do header
        pdf.set_draw_color(180, 180, 180)   # borda suave
        pdf.set_line_width(0.2)

        x_base = pdf.l_margin
        y_top  = pdf.get_y()
        cur_x  = x_base

        for i, head in enumerate(headers):
            pdf.set_xy(cur_x, y_top)
            pdf.cell(widths[i], header_h, sanitize_text(head), border=1, align="C", fill=True)
            cur_x += widths[i]
        pdf.ln(header_h)

        # Corpo
        set_font(10, False)

        def _draw_header_again():
            set_font(10, True)
            pdf.set_fill_color(242, 242, 242)
            pdf.set_draw_color(180, 180, 180)
            pdf.set_line_width(0.2)

            xh = pdf.l_margin
            yh = pdf.get_y()
            cx = xh
            for j, h in enumerate(headers):
                pdf.set_xy(cx, yh)
                pdf.cell(widths[j], header_h, sanitize_text(h), border=1, align="C", fill=True)
                cx += widths[j]
            pdf.ln(header_h)
            set_font(10, False)

        for row in rows:
            wrapped_cols = []
            max_lines = 1
            for i, val in enumerate(row):
                content_w = max(1, widths[i] - 2*pad)
                val = sanitize_text(val or "")
                lines = wrap_text(val or "", pdf, content_w)
                wrapped_cols.append(lines)
                max_lines = max(max_lines, len(lines))

            row_h = max_lines * cell_h + 2*pad

            if pdf.get_y() + row_h > pdf.page_break_trigger:
                pdf.add_page()
                _draw_header_again()

            y_row = pdf.get_y()
            cx = pdf.l_margin
            for i, lines in enumerate(wrapped_cols):
                pdf.rect(cx, y_row, widths[i], row_h)

                x_text = cx + pad
                y_text = y_row + pad
                for ln in lines:
                    pdf.set_xy(x_text, y_text)
                    pdf.cell(widths[i] - 2*pad, cell_h, ln)
                    y_text += cell_h

                cx += widths[i]

            pdf.ln(row_h)

    # --------------------------
    # Seção 2 — Cronograma (tabela como no print)
    # --------------------------
    bar_title("2. Cronograma e Regras Técnicas")

    # Larguras calibradas p/ quebrar "dias útil" e "sem nota"
    w1 = 52   # Prazo Envio
    w2 = 35   # Validade
    w3 = 35   # XML / Versão
    w4 = 30   # Nota Fiscal
    w5 = (pdf.w - pdf.l_margin - pdf.r_margin) - (w1 + w2 + w3 + w4)  # restante (~28mm)
    widths = [w1, w2, w3, w4, w5]

    headers = ["Prazo Envio", "Validade Guia", "XML / Versão", "Nota Fiscal", "Fluxo NF"]

    
    xml_flag = safe_get(dados, "xml") or "—"
    xml_ver  = safe_get(dados, "versao_xml") or "—"
    xml_composto = f"{xml_flag} / {xml_ver}"
    xml_composto = re.sub(r"(?<=\w)/(?!\s)", " / ", xml_composto)


    row = [
        safe_get(dados, "envio"),      # ex. "Data de envio: 01 ao 05 dias útil"
        safe_get(dados, "validade"),   # "90"
        xml_composto,                  # "Sim / 4.01.00"
        safe_get(dados, "nf"),         # "Não"
        safe_get(dados, "fluxo_nf"),   # "Envia XML sem nota"
    ]
    table(headers, [row], widths, header_h=8.0, cell_h=6.0, pad=2.0)
    pdf.ln(2.0)

    # --------------------------
    # Observações Críticas — multipágina (com parágrafos + bullets)
    # --------------------------
    bar_title("Observações Críticas")

    obs_text = safe_get(dados, "observacoes")
    left_margin = pdf.l_margin
    width = CONTENT_W
    line_h = 6.6
    padding = 1.8
    bullet_indent = 4.0

    usable_w = width - 2 * padding
    set_font(10, False)

    wrapped_lines = build_wrapped_lines(obs_text, pdf, usable_w, line_h, bullet_indent=bullet_indent)

    i = 0
    while i < len(wrapped_lines):
        y_top = pdf.get_y()
        space = pdf.page_break_trigger - y_top
        avail_h = max(0.0, space - 2 * padding - 0.5)
        lines_per_page = int(avail_h // line_h) if avail_h > 0 else 0
        if lines_per_page <= 0:
            pdf.add_page()
            continue

        end = min(len(wrapped_lines), i + lines_per_page)
        slice_lines = wrapped_lines[i:end]

        box_h = 2 * padding + len(slice_lines) * line_h
        pdf.rect(left_margin, y_top, width, box_h)

        x_text_base = left_margin + padding
        y_text = y_top + padding
        for (ln_text, indent_mm) in slice_lines:
            pdf.set_xy(x_text_base + indent_mm, y_text)
            pdf.cell(usable_w - indent_mm, line_h, ln_text)
            y_text += line_h

        pdf.set_y(y_top + box_h)
        i = end

        if i < len(wrapped_lines) and pdf.get_y() + line_h > pdf.page_break_trigger:
            pdf.add_page()

    # --------------------------
    # Retorno seguro (bytes)
    # --------------------------
    result = pdf.output(dest="S")
    if isinstance(result, str):        # FPDF 1.x
        try:
            result = result.encode("latin-1")
        except Exception:
            result = result.encode("latin-1", "ignore")
    return result

# ============================================================
# 10. UI COMPONENTS
# ============================================================
def ui_card_start(title: str):
    st.markdown(f"""
        <div class='card'>
            <div class='card-title'>{ui_text(title)}</div>
    """, unsafe_allow_html=True)

def ui_card_end():
    st.markdown("</div>", unsafe_allow_html=True)

def ui_section_title(text: str):
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
            {ui_text(text).upper()}
        </div>
        """,
        unsafe_allow_html=True
    )

def ui_info_line(label: str, value: str):
    st.markdown(
        f"""
        <div style="margin:6px 0; font-size:15px; line-height:1.5;">
            <strong>{ui_text(label)}:</strong>
            <span>{ui_text(value)}</span>
        </div>
        """,
        unsafe_allow_html=True
    )

def ui_block_info(title: str, content: str):
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
# 11. PÁGINA — CADASTRO / EDIÇÃO DE CONVÊNIOS
# ============================================================
def page_cadastro():
    dados_atuais, _ = db.load(force=True)
    dados_atuais = list(dados_atuais)

    ui_card_start("📝 Cadastro de Convênio")

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
            (c for c in dados_atuais if str(c.get('id')) == str(conv_id)),
            None
        )

    ui_card_end()

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
            xml = st.radio("Envia XML?", OPCOES_XML, index=OPCOES_XML.index(valor_xml))

            valor_nf = safe_get(dados_conv, "nf")
            if valor_nf not in OPCOES_NF:
                valor_nf = "Sim"
            nf = st.radio("Exige Nota Fiscal?", OPCOES_NF, index=OPCOES_NF.index(valor_nf))

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

        config_gerador = st.text_area("Configuração do Gerador XML", value=safe_get(dados_conv, "config_gerador"))
        doc_digitalizacao = st.text_area("Digitalização e Documentação", value=safe_get(dados_conv, "doc_digitalizacao"))
        observacoes = st.text_area("Observações Críticas", value=safe_get(dados_conv, "observacoes"))

        submit = st.form_submit_button("💾 Salvar Dados")

        if submit:
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
                db._cache_time = 0.0

                # LIMPA ESTADO DO STREAMLIT
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
# 12. PÁGINAS — CONSULTA & VISUALIZAR BANCO
# ============================================================
def page_consulta(dados_atuais):
    if not dados_atuais:
        st.info("Nenhum convênio cadastrado.")
        return

    opcoes = sorted([f"{safe_get(c,'id')} || {safe_get(c,'nome')}" for c in dados_atuais])
    escolha = st.selectbox("Selecione o convênio:", opcoes)
    conv_id = escolha.split(" || ")[0]

    dados = next((c for c in dados_atuais if str(c.get("id")) == str(conv_id)), None)
    if not dados:
        st.error("Erro: convênio não encontrado no banco.")
        return

    ui_section_title(safe_get(dados, "nome"))

    ui_card_start("🧾 Dados de Identificação")
    ui_info_line("Empresa", safe_get(dados, "empresa"))
    ui_info_line("Código", safe_get(dados, "codigo"))
    ui_info_line("Sistema", safe_get(dados, "sistema_utilizado"))
    ui_info_line("Prazo de Retorno", safe_get(dados, "prazo_retorno"))
    ui_card_end()

    ui_card_start("🔐 Acesso ao Portal")
    ui_info_line("Portal", safe_get(dados, "site"))
    ui_info_line("Login", safe_get(dados, "login"))
    ui_info_line("Senha", safe_get(dados, "senha"))
    ui_card_end()

    ui_card_start("📦 Regras Técnicas")
    ui_info_line("Prazo Envio", safe_get(dados, "envio"))
    ui_info_line("Validade da Guia", safe_get(dados, "validade"))
    ui_info_line("Envia XML?", safe_get(dados, "xml"))
    ui_info_line("Versão XML", safe_get(dados, "versao_xml"))
    ui_info_line("Exige NF?", safe_get(dados, "nf"))
    ui_info_line("Fluxo da Nota", safe_get(dados, "fluxo_nf"))
    ui_card_end()

    ui_block_info("⚙️ Configuração XML", safe_get(dados, "config_gerador"))
    ui_block_info("🗂 Digitalização e Documentação", safe_get(dados, "doc_digitalizacao"))
    ui_block_info("⚠️ Observações Críticas", safe_get(dados, "observacoes"))

    st.caption("Manual de Faturamento — Visualização Premium")

def page_visualizar_banco(dados_atuais):
    ui_card_start("📋 Banco de Dados Completo")
    if dados_atuais:
        df = pd.DataFrame(dados_atuais)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("⚠️ Banco vazio.")
    ui_card_end()

# ============================================================
# 13. MAIN — set_page_config vem ANTES de qualquer render
# ============================================================
def main():
    st.set_page_config(page_title="💼 Manual de Faturamento", layout="wide")
    # Aplica CSS e header somente após set_page_config
    st.markdown(CSS_GLOBAL, unsafe_allow_html=True)

    dados_atuais, _ = db.load()

    st.sidebar.title("📚 Navegação")
    menu = st.sidebar.radio(
        "Selecione a página:", ["Cadastrar / Editar", "Consulta de Convênios", "Visualizar Banco"]
    )
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔄 Atualizar Sistema")
    if st.sidebar.button("Recarregar"):
        st.rerun()

    if menu == "Cadastrar / Editar":
        page_cadastro()
    elif menu == "Consulta de Convênios":
        page_consulta(dados_atuais)
    elif menu == "Visualizar Banco":
        page_visualizar_banco(dados_atuais)

    st.markdown(
        """
        <br><br>
        <div style='text-align:center; color:#777; font-size:13px; padding:10px;'>
            © 2026 — Manual de Faturamento<br>
            Desenvolvido com design corporativo Microsoft/MV
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
