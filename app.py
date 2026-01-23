
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
import io
import json
import time
import base64
import random
import unicodedata

import requests
import pandas as pd
from fpdf import FPDF
from PIL import Image
import streamlit as st
from rotinas_module import RotinasModule

from streamlit_quill import st_quill
from streamlit_paste_button import paste_image_button

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
    
        # Pode vir vazio; garante string
        decoded_b64 = body.get("content") or ""
        decoded = base64.b64decode(decoded_b64).decode("utf-8")
    
        # Auto-healing p/ arquivo vazio ou inválido
        if not decoded.strip():
            data = []
        else:
            try:
                data = json.loads(decoded)
            except json.JSONDecodeError:
                # remove possíveis BOMs e tenta de novo
                decoded = decoded.lstrip("\ufeff")
                try:
                    data = json.loads(decoded)
                except json.JSONDecodeError:
                    # fallback seguro: considera base vazia
                    data = []
    
        # Garante tipo lista (se vier dict por engano)
        if not isinstance(data, list):
            data = []
    
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

ROTINAS_FILE_PATH = "rotinas.json"

db_rotinas = GitHubJSON(
    token=GITHUB_TOKEN,
    owner=REPO_OWNER,
    repo=REPO_NAME,
    path=ROTINAS_FILE_PATH,
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

# Opções de setor para as Rotinas do Setor
SETORES_ROTINA = [
    "Apoio e Controle",
    "Faturamento - AMHP",
    "Remessa - AMHP",
    "Integralis - Faturamento",
    "Integralis - Remessa",
    "CTI - Faturamento",
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

def image_to_base64(img):
    if img is None: return None
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def clean_html(raw_html):
    """Limpa tags HTML para o PDF não bugar"""
    if not raw_html: return ""
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html)


def extract_images_from_html(html_content):
    """
    Extrai imagens base64 de tags <img> do HTML e retorna tupla (texto_sem_imagens, lista_imagens)
    """
    if not html_content:
        return html_content, []

    images = []

    # Regex para encontrar tags <img src="data:image/...;base64,DATA">
    img_pattern = r'<img[^>]+src="data:image/([^;]+);base64,([^"]+)"[^>]*>'

    def replace_img(match):
        image_format = match.group(1)  # png, jpeg, etc
        base64_data = match.group(2)

        try:
            # Decodifica base64
            img_data = base64.b64decode(base64_data)
            # Cria objeto Image do Pillow
            img = Image.open(io.BytesIO(img_data))
            images.append(img)
            # Retorna marcador de texto para manter espaçamento
            return "\n[IMAGEM]\n"
        except Exception as e:
            print(f"Erro ao processar imagem: {e}")
            return ""

    # Substitui tags de imagem por marcador
    html_without_images = re.sub(img_pattern, replace_img, html_content)

    return html_without_images, images


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
    Layout: título azul, Seção 1, Seção 2 (Tabela) e Observações Críticas.
    """
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(15, 12, 15)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    BLUE = (31, 73, 125)
    GREY_BAR = (230, 230, 230)
    TEXT = (0, 0, 0)
    CONTENT_W = pdf.w - pdf.l_margin - pdf.r_margin
    
    # 1. ATIVAR FONTE PARA CÁLCULOS IMEDIATAMENTE
    FONT_FAMILY = _pdf_set_fonts(pdf)
    pdf.set_font(FONT_FAMILY, '', 10) 
    
    line_h = 6.6
    padding = 1.8
    bullet_indent = 4.0
    usable_w = CONTENT_W - 2 * padding

    # 2. PROCESSAMENTO DO TEXTO RICO E IMAGENS
    obs_text_raw = safe_get(dados, "observacoes")
    # Extrai imagens antes de limpar HTML
    obs_text_with_markers, obs_images = extract_images_from_html(obs_text_raw)
    obs_text = clean_html(obs_text_with_markers)
    wrapped_lines = build_wrapped_lines(obs_text, pdf, usable_w, line_h, bullet_indent=bullet_indent)

    # ---------- HELPERS INTERNOS ----------
    def apply_font(size=10, bold=False):
        style = "B" if bold else ""
        try:
            pdf.set_font(FONT_FAMILY, style, size)
        except:
            pdf.set_font("Helvetica", style, size)
            
    def bar_title(texto, top_margin=3, height=8):
        pdf.ln(top_margin)
        pdf.set_fill_color(*GREY_BAR)
        apply_font(12, True)
        pdf.cell(0, height, f" {texto.upper()}", ln=1, fill=True)
        pdf.ln(1.5)

    def one_column_info(pares, label_w=30, line_h_val=6.8, gap_y=1.6, val_size=10):
        x = pdf.l_margin
        y = pdf.get_y()
        u_w = CONTENT_W - label_w
        for (label, value) in pares:
            label = label or ""
            value = value or ""
            apply_font(val_size, False) 
            value = sanitize_text(value)
            lines = wrap_text(value, pdf, max(1, u_w))
            needed_h = max(1, len(lines)) * line_h_val
            if y + needed_h > pdf.page_break_trigger:
                pdf.add_page()
                apply_font(val_size, False)
                y = pdf.get_y()
            apply_font(10, True) 
            pdf.set_xy(x, y)
            pdf.cell(label_w, line_h_val, f"{label}:")
            apply_font(val_size, False) 
            pdf.set_xy(x + label_w, y)
            pdf.cell(u_w, line_h_val, lines[0] if lines else "")
            for i in range(1, len(lines)):
                pdf.set_xy(x + label_w, y + i * line_h_val)
                pdf.cell(u_w, line_h_val, lines[i])
            y = y + needed_h + gap_y
        pdf.set_y(y)

    def table(headers, rows, widths, header_h=8.0, cell_h=6.0, pad=2.0):
        apply_font(10, True)
        pdf.set_fill_color(242, 242, 242)
        pdf.set_draw_color(180, 180, 180)
        x_base = pdf.l_margin
        y_top = pdf.get_y()
        cur_x = x_base
        for i, head in enumerate(headers):
            pdf.set_xy(cur_x, y_top)
            pdf.cell(widths[i], header_h, sanitize_text(head), border=1, align="C", fill=True)
            cur_x += widths[i]
        pdf.ln(header_h)

        apply_font(10, False)
        for row_data in rows:
            wrapped_cols = []
            max_l = 1
            for i, val in enumerate(row_data):
                content_w = max(1, widths[i] - 2*pad)
                lines = wrap_text(sanitize_text(val or ""), pdf, content_w)
                wrapped_cols.append(lines)
                max_l = max(max_l, len(lines))
            row_h = max_l * cell_h + 2*pad
            if pdf.get_y() + row_h > pdf.page_break_trigger:
                pdf.add_page()
                apply_font(10, False)
            y_row = pdf.get_y()
            cx = pdf.l_margin
            for i, lines in enumerate(wrapped_cols):
                pdf.rect(cx, y_row, widths[i], row_h)
                yt = y_row + pad
                for ln in lines:
                    pdf.set_xy(cx + pad, yt)
                    pdf.cell(widths[i] - 2*pad, cell_h, ln)
                    yt += cell_h
                cx += widths[i]
            pdf.ln(row_h)

    # ---------- RENDERIZAÇÃO ----------
    nome_conv = sanitize_text(safe_get(dados, "nome")).upper()
    pdf.set_fill_color(*BLUE)
    pdf.set_text_color(255, 255, 255)
    apply_font(18, True)
    pdf.cell(0, 14, f"MANUAL: {nome_conv}" if nome_conv else "GUIA TÉCNICA", ln=1, align="C", fill=True)
    pdf.set_text_color(*TEXT)
    pdf.ln(5)

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
    one_column_info(pares_unicos)

    bar_title("2. Cronograma e Regras Técnicas")
    w1, w2, w3, w4 = 52, 35, 35, 30
    w5 = CONTENT_W - (w1 + w2 + w3 + w4)
    widths = [w1, w2, w3, w4, w5]
    headers = ["Prazo Envio", "Validade Guia", "XML / Versão", "Nota Fiscal", "Fluxo NF"]
    
    xml_flag = safe_get(dados, "xml") or "—"
    xml_ver = safe_get(dados, "versao_xml") or "—"
    row = [safe_get(dados, "envio"), safe_get(dados, "validade"), f"{xml_flag} / {xml_ver}", safe_get(dados, "nf"), safe_get(dados, "fluxo_nf")]
    table(headers, [row], widths)

    bar_title("Observações Críticas")
    apply_font(10, False)

    # Renderiza texto e imagens
    idx = 0
    img_idx = 0
    while idx < len(wrapped_lines):
        # Verifica se a linha atual contém marcador de imagem
        if idx < len(wrapped_lines) and "[IMAGEM]" in wrapped_lines[idx][0]:
            # Adiciona imagem se houver
            if img_idx < len(obs_images):
                img = obs_images[img_idx]
                # Salva imagem temporariamente
                temp_img_path = f"/tmp/temp_img_{img_idx}.png"
                img.save(temp_img_path, "PNG")

                # Calcula dimensões para caber na largura disponível
                img_width = CONTENT_W - 10  # margem de 5mm de cada lado
                aspect_ratio = img.height / img.width
                img_height = img_width * aspect_ratio

                # Verifica se cabe na página
                y_curr = pdf.get_y()
                if y_curr + img_height > pdf.page_break_trigger:
                    pdf.add_page()
                    apply_font(10, False)
                    y_curr = pdf.get_y()

                # Adiciona imagem centralizada
                x_img = pdf.l_margin + 5
                pdf.image(temp_img_path, x=x_img, y=y_curr, w=img_width)
                pdf.set_y(y_curr + img_height + 5)  # espaço após imagem

                # Remove arquivo temporário
                try:
                    os.remove(temp_img_path)
                except:
                    pass

                img_idx += 1
            # Pula linha com marcador
            idx += 1
            continue

        y_curr = pdf.get_y()
        espaco_livre = pdf.page_break_trigger - y_curr
        linhas_possiveis = int((espaco_livre - 2 * padding) // line_h)
        if linhas_possiveis <= 0:
            pdf.add_page()
            apply_font(10, False)
            y_curr = pdf.get_y()
            linhas_possiveis = int((pdf.page_break_trigger - y_curr - 2 * padding) // line_h)

        fim = min(len(wrapped_lines), idx + linhas_possiveis)
        chunk = wrapped_lines[idx:fim]

        # Filtra linhas com marcador de imagem
        chunk = [(txt, ind) for (txt, ind) in chunk if "[IMAGEM]" not in txt]
        if not chunk:
            idx = fim
            continue

        box_h = 2 * padding + len(chunk) * line_h
        pdf.rect(pdf.l_margin, y_curr, CONTENT_W, box_h)
        y_txt = y_curr + padding
        for (txt, ind) in chunk:
            pdf.set_xy(pdf.l_margin + padding + ind, y_txt)
            pdf.cell(usable_w - ind, line_h, txt)
            y_txt += line_h
        pdf.set_y(y_curr + box_h)
        idx = fim

    # fpdf2 retorna bytearray, converter para bytes
    return bytes(pdf.output())


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

# ------------------------------------------------------------
# FUNÇÕES DE APOIO (Coloque antes da def page_cadastro)
# ------------------------------------------------------------
def image_to_base64(img):
    """Converte objeto PIL Image para string Base64 para salvar no JSON"""
    if img is None:
        return ""
    import io
    buffered = io.BytesIO()
    # Otimização: Redimensiona se for muito grande para não travar o JSON no GitHub
    if img.width > 1200:
        img.thumbnail((1200, 1200))
    img.save(buffered, format="PNG", optimize=True)
    return base64.b64encode(buffered.getvalue()).decode()

def clean_html(raw_html):
    """Remove tags HTML para processamento de texto puro (usado no PDF)"""
    if not raw_html: return ""
    cleanr = re.compile('<.*?>|&nbsp;')
    cleantext = re.sub(cleanr, ' ', raw_html)
    return re.sub(r' +', ' ', cleantext).strip()

# ------------------------------------------------------------
# MÓDULO DE CADASTRO COMPLETO
# ------------------------------------------------------------
# ------------------------------------------------------------
# MÓDULO DE CADASTRO COMPLETO (REINTEGRADO XML/NF)
# ------------------------------------------------------------
def page_cadastro():
    from streamlit_quill import st_quill
    from streamlit_paste_button import paste_image_button

    dados_atuais, _ = db.load(force=True)
    dados_atuais = list(dados_atuais)

    ui_card_start("📝 Gestão de Convênios")

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

    form_key = f"form_premium_{conv_id}" if conv_id else "form_premium_novo"

    with st.form(key=form_key):
        # --- BLOCO 1: IDENTIFICAÇÃO ---
        st.markdown("##### 🏢 Identificação e Acesso")
        col1, col2, col3 = st.columns(3)

        with col1:
            nome = st.text_input("Nome do Convênio", value=safe_get(dados_conv, "nome"))
            codigo = st.text_input("Código", value=safe_get(dados_conv, "codigo"))
            
            valor_empresa = safe_get(dados_conv, "empresa")
            empresa = st.selectbox("Empresa", EMPRESAS_FATURAMENTO, 
                                 index=EMPRESAS_FATURAMENTO.index(valor_empresa) if valor_empresa in EMPRESAS_FATURAMENTO else 0)

        with col2:
            site = st.text_input("Site/Portal", value=safe_get(dados_conv, "site"))
            login = st.text_input("Login", value=safe_get(dados_conv, "login"))
            senha = st.text_input("Senha", value=safe_get(dados_conv, "senha"))

        with col3:
            sistema = st.selectbox("Sistema", SISTEMAS,
                                 index=SISTEMAS.index(safe_get(dados_conv, "sistema_utilizado")) if safe_get(dados_conv, "sistema_utilizado") in SISTEMAS else 0)
            retorno = st.text_input("Prazo Retorno", value=safe_get(dados_conv, "prazo_retorno"))
            envio = st.text_input("Prazo Envio", value=safe_get(dados_conv, "envio"))

        st.markdown("---")

        # --- BLOCO 2: REGRAS TÉCNICAS (XML E NF REINTEGRADOS) ---
        st.markdown("##### ⚙️ Regras Técnicas (XML e Nota Fiscal)")
        col_xml, col_nf, col_fluxo = st.columns([1, 1, 2])

        with col_xml:
            valor_xml = safe_get(dados_conv, "xml") or "Sim"
            xml = st.radio("Envia XML?", OPCOES_XML, index=OPCOES_XML.index(valor_xml), horizontal=True)
            
            valor_versao = safe_get(dados_conv, "versao_xml")
            versao_xml = st.selectbox("Versão TISS", VERSOES_TISS,
                                    index=VERSOES_TISS.index(valor_versao) if valor_versao in VERSOES_TISS else 0)

        with col_nf:
            valor_nf = safe_get(dados_conv, "nf") or "Não"
            nf = st.radio("Exige NF?", OPCOES_NF, index=OPCOES_NF.index(valor_nf), horizontal=True)
            validade = st.text_input("Validade da Guia (Dias)", value=safe_get(dados_conv, "validade"))

        with col_fluxo:
            valor_fluxo = safe_get(dados_conv, "fluxo_nf") or OPCOES_FLUXO_NF[0]
            fluxo_nf = st.selectbox("Fluxo da Nota Fiscal", OPCOES_FLUXO_NF,
                                  index=OPCOES_FLUXO_NF.index(valor_fluxo) if valor_fluxo in OPCOES_FLUXO_NF else 0)

        st.markdown("---")
        
        # --- BLOCO 3: EDITOR RICO ---
        st.markdown("##### 🖋️ Observações Críticas")
        observacoes_html = st_quill(
            value=safe_get(dados_conv, "observacoes"),
            placeholder="Digite as regras detalhadas de faturamento aqui...",
            key=f"quill_{conv_id}"
        )

        # --- BLOCO 4: PRINT / IMAGEM ---
        st.markdown("##### 📸 Print de Tela / Evidência")
        c_paste, c_preview = st.columns([1, 1])
        
        with c_paste:
            st.info("Clique no botão abaixo e cole (Ctrl+V) o print.")
            pasted_img = paste_image_button(label="📋 Colar Imagem", key=f"paste_btn_{conv_id}")
        
        img_b64_salva = safe_get(dados_conv, "print_b64")
        
        if pasted_img.image_data is not None:
            with c_preview:
                st.image(pasted_img.image_data, caption="Nova Imagem", use_container_width=True)
            img_para_salvar = image_to_base64(pasted_img.image_data)
        elif img_b64_salva:
            with c_preview:
                st.image(base64.b64decode(img_b64_salva), caption="Imagem Atual", use_container_width=True)
            img_para_salvar = img_b64_salva
        else:
            img_para_salvar = ""

        st.markdown("<br>", unsafe_allow_html=True)
        submit = st.form_submit_button("💾 SALVAR MANUAL COMPLETO", use_container_width=True)

        if submit:
            if not nome:
                st.error("Nome do convênio é obrigatório.")
            else:
                novo_reg = {
                    "id": int(conv_id) if conv_id else generate_id(dados_atuais),
                    "nome": nome,
                    "codigo": codigo,
                    "empresa": empresa,
                    "site": site,
                    "login": login,
                    "senha": senha,
                    "sistema_utilizado": sistema,
                    "prazo_retorno": retorno,
                    "envio": envio,
                    "validade": validade,
                    "xml": xml,
                    "versao_xml": versao_xml,
                    "nf": nf,
                    "fluxo_nf": fluxo_nf,
                    "observacoes": observacoes_html,
                    "print_b64": img_para_salvar,
                    # Mantém campos antigos se existirem no banco para não perder histórico
                    "config_gerador": safe_get(dados_conv, "config_gerador"),
                    "doc_digitalizacao": safe_get(dados_conv, "doc_digitalizacao")
                }

                if conv_id is None:
                    dados_atuais.append(novo_reg)
                else:
                    for i, c in enumerate(dados_atuais):
                        if str(c.get("id")) == str(conv_id):
                            dados_atuais[i] = novo_reg
                            break

                if db.save(dados_atuais):
                    st.success("✔ Dados atualizados com sucesso!")
                    time.sleep(0.8)
                    st.rerun()



    # BOTÃO PDF
    if dados_conv:
        st.download_button(
            "📥 Baixar PDF do Convênio",
            gerar_pdf(dados_conv),
            file_name=f"Manual_{safe_get(dados_conv,'nome')}.pdf",
            mime="application/pdf"
        )

        # ==============================
        # 🗑️ EXCLUSÃO PERMANENTE — CONVÊNIO
        # ==============================
        with st.expander("🗑️ Excluir convênio (permanente)", expanded=False):
            st.warning(
                "Esta ação **não pode ser desfeita**. "
                "Para confirmar, digite o **ID** do convênio e clique em Excluir.",
                icon="⚠️"
            )

            # Garante o ID como string (usa o do registro salvo quando existir)
            conv_id_str = str(dados_conv.get("id") if isinstance(dados_conv, dict) else conv_id or "").strip()

            confirm_val = st.text_input(
                f"Confirmação: digite **{conv_id_str}**",
                key=f"confirm_del_conv_{conv_id_str}"
            )

            can_delete = confirm_val.strip() == conv_id_str and bool(conv_id_str)

            if st.button(
                "Excluir convênio **permanentemente**",
                type="primary",
                disabled=not can_delete,
                key=f"btn_del_conv_{conv_id_str}"
            ):
                try:
                    def _update(data):
                        # remove o registro cujo id == conv_id_str
                        return [c for c in (data or []) if str(c.get("id")) != conv_id_str]

                    # Atualiza no GitHub de forma atômica (SHA locking)
                    db.update(_update)

                    st.success(f"✔ Convênio {conv_id_str} excluído com sucesso!")

                    # Limpa caches e estado da UI; recarrega a app
                    db._cache_data = None
                    db._cache_sha = None
                    db._cache_time = 0.0
                    st.session_state.clear()
                    time.sleep(1)
                    st.rerun()

                except Exception as e:
                    st.error(f"Falha ao excluir convênio {conv_id_str}: {e}")   
    


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


# >>>>>>>>>>>>> INSTÂNCIA DO MÓDULO DE ROTINAS <<<<<<<<<<<<
rotinas_module = RotinasModule(
    db_rotinas=db_rotinas,
    sanitize_text=sanitize_text,
    build_wrapped_lines=build_wrapped_lines,
    _pdf_set_fonts=_pdf_set_fonts,
    generate_id=generate_id,
    safe_get=safe_get,
    primary_color=PRIMARY_COLOR,
    setores_opcoes=SETORES_ROTINA,  
)

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
        "Selecione a página:",
        ["Cadastrar / Editar", "Consulta de Convênios", "Visualizar Banco", "Rotinas do Setor"]
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
    elif menu == "Rotinas do Setor":
        rotinas_module.page()

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
