
# ============================================================
#  APP.PY — PARTE 1
#  Imports • Config • GitHub Functions • Design Microsoft/MV
# ============================================================

import streamlit as st
import requests
import base64
import json
import os
import pandas as pd
from fpdf import FPDF

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

        /* Fundo geral */
        body {{
            background-color: {BG_LIGHT};
        }}

        /* Títulos */
        .main-title {{
            font-size: 36px;
            font-weight: 700;
            color: {PRIMARY_COLOR};
            padding: 10px 0 20px 0;
        }}

        /* Cards corporativos */
        .card {{
            background: white;
            padding: 22px;
            border-radius: 12px;
            border: 1px solid {GREY_BORDER};
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            margin-bottom: 22px;
        }}

        .card-title {{
            font-size: 22px;
            font-weight: 700;
            color: {PRIMARY_COLOR};
            margin-bottom: 12px;
        }}

        .info-line {{
            font-size: 15px;
            padding: 4px 0;
            color: {TEXT_DARK};
        }}
        .value {{
            font-weight: 600;
        }}

    </style>
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
#  APP.PY — PARTE 2
#  Função PDF Premium (UTF-8 + Layout MV)
#  Menu + Inicialização do App
# ============================================================

# -----------------------------------------
#     GERADOR DE PDF — LAYOUT PREMIUM
# -----------------------------------------
def gerar_pdf(dados):
    pdf = FPDF()
    pdf.add_page()

    # Fontes UTF‑8
    fonte_normal = "DejaVuSans.ttf"
    fonte_bold = "DejaVuSans-Bold.ttf"

    if os.path.exists(fonte_normal):
        pdf.add_font("DejaVu", "", fonte_normal, uni=True)
        fonte_principal = "DejaVu"
        if os.path.exists(fonte_bold):
            pdf.add_font("DejaVu", "B", fonte_bold, uni=True)
            estilo_b = "B"
        else:
            estilo_b = ""
    else:
        fonte_principal = "Helvetica"
        estilo_b = "B"

    # Cabeçalho
    pdf.set_fill_color(31, 73, 125)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font(fonte_principal, estilo_b, 16)
    pdf.cell(0, 15, f"GUIA TÉCNICA: {dados['nome'].upper()}", ln=True, align='C', fill=True)
    pdf.ln(5)

    # Seção 1 – Identificação
    pdf.set_text_color(0, 0, 0)
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font(fonte_principal, estilo_b, 11)
    pdf.cell(0, 8, " 1. DADOS DE IDENTIFICAÇÃO E ACESSO", ln=True, fill=True)

    pdf.set_font(fonte_principal, "", 10)
    pdf.ln(2)
    pdf.write(7, f"Empresa: {dados.get('empresa','N/A')} | Código: {dados.get('codigo','N/A')}\n")
    pdf.write(7, f"Portal: {dados['site']}\n")
    pdf.write(7, f"Login: {dados['login']}  |  Senha: {dados['senha']}\n")
    pdf.write(7, f"Sistema: {dados.get('sistema_utilizado','N/A')} | Retorno: {dados.get('prazo_retorno','N/A')}\n")
    pdf.ln(5)

    # Seção 2 – Tabela TISS
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font(fonte_principal, estilo_b, 11)
    pdf.cell(0, 8, " 2. CRONOGRAMA E REGRAS TÉCNICAS", ln=True, fill=True)
    pdf.ln(2)

    pdf.set_font(fonte_principal, estilo_b, 8)
    pdf.cell(50, 8, "Prazo Envio", 1, 0, 'C')
    pdf.cell(30, 8, "Validade Guia", 1, 0, 'C')
    pdf.cell(25, 8, "XML / Versão", 1, 0, 'C')
    pdf.cell(25, 8, "Nota Fiscal", 1, 0, 'C')
    pdf.cell(60, 8, "Fluxo NF", 1, 1, 'C')

    pdf.set_font(fonte_principal, "", 8)
    pdf.cell(50, 8, dados["envio"][:30], 1, 0, 'C')
    pdf.cell(30, 8, f"{dados['validade']} dias", 1, 0, 'C')
    pdf.cell(25, 8, f"{dados['xml']} / {dados.get('versao_xml','-')}", 1, 0, 'C')
    pdf.cell(25, 8, dados['nf'], 1, 0, 'C')
    pdf.cell(60, 8, dados.get('fluxo_nf','N/A')[:35], 1, 1, 'C')
    pdf.ln(5)

    # Blocos extras
    def bloco(titulo, conteudo):
        if conteudo:
            pdf.set_font(fonte_principal, estilo_b, 11)
            pdf.set_fill_color(240, 240, 240)
            pdf.cell(0, 7, f" {titulo}", ln=True, fill=True)

            pdf.set_font(fonte_principal, "", 9)
            pdf.multi_cell(0, 5, conteudo, border=1)
            pdf.ln(3)

    bloco("CONFIGURAÇÃO DO GERADOR XML", dados.get("config_gerador",""))
    bloco("DIGITALIZAÇÃO E DOCUMENTAÇÃO", dados.get("doc_digitalizacao",""))
    bloco("OBSERVAÇÕES CRÍTICAS", dados["observacoes"])

    # Rodapé
    pdf.set_y(-20)
    pdf.set_text_color(120,120,120)
    pdf.set_font(fonte_principal, "", 8)
    pdf.cell(0, 10, "GABMA Consultoria - Sistema Técnico de Convênios", align='C')

    return bytes(pdf.output())


# -----------------------------------------
#       APP – INÍCIO
# -----------------------------------------

st.set_page_config(page_title="GABMA – Sistema Técnico", layout="wide")

st.markdown(f"<div class='main-title'>💼 Sistema de Gestão GABMA</div>", unsafe_allow_html=True)

dados_atuais, sha_atual = buscar_dados_github()

# MENU LATERAL
menu = st.sidebar.radio(
    "Navegação",
    ["Cadastrar / Editar", "Consulta de Convênios", "Visualizar Banco"]
)


# ============================================================
#  APP.PY — PARTE 3
#  Cadastro / Consulta Premium / Visualizar Banco
# ============================================================

# ============================================================
#           TELA — CADASTRAR / EDITAR CONVÊNIO
# ============================================================
if menu == "Cadastrar / Editar":

    st.markdown("<div class='card'><div class='card-title'>📝 Cadastro de Convênio</div>", unsafe_allow_html=True)

    nomes = ["+ Novo Convênio"] + sorted([c["nome"] for c in dados_atuais])
    escolha = st.selectbox("Selecione um convênio:", nomes)

    dados_conv = next((c for c in dados_atuais if c["nome"] == escolha), None)

    # Lista oficial das versões TISS completas
    VERSOES_TISS = [
        "4.03.00",
        "4.02.00",
        "4.01.00",
        "01.06.00",
        "3.05.00",
        "3.04.01"
    ]

    with st.form("form_cadastro"):
        
        col1, col2, col3 = st.columns(3)

        # ------- COLUNA 1 -------
        with col1:
            nome = st.text_input("Nome do Convênio", value=dados_conv["nome"] if dados_conv else "")
            codigo = st.text_input("Código", value=dados_conv.get("codigo", "") if dados_conv else "")
            empresa = st.text_input("Empresa Faturamento", value=dados_conv.get("empresa", "") if dados_conv else "")
            sistema = st.selectbox("Sistema", ["Orizon", "Benner", "Maida", "Facil", "Visual TISS", "Próprio"])

        # ------- COLUNA 2 -------
        with col2:
            site = st.text_input("Site/Portal", value=dados_conv["site"] if dados_conv else "")
            login = st.text_input("Login", value=dados_conv["login"] if dados_conv else "")
            senha = st.text_input("Senha", value=dados_conv["senha"] if dados_conv else "")
            retorno = st.text_input("Prazo Retorno", value=dados_conv.get("prazo_retorno", "") if dados_conv else "")

        # ------- COLUNA 3 -------
        with col3:
            envio = st.text_input("Prazo Envio", value=dados_conv["envio"] if dados_conv else "")
            validade = st.text_input("Validade Guia", value=dados_conv["validade"] if dados_conv else "")
            xml = st.radio("Envia XML?", ["Sim", "Não"], index=0 if not dados_conv or dados_conv["xml"] == "Sim" else 1)
            nf = st.radio("Exige NF?", ["Sim", "Não"], index=0 if not dados_conv or dados_conv["nf"] == "Sim" else 1)

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ------- LINHA ABAIXO (VERSÃO TISS E FLUXO) -------
        col_a, col_b = st.columns(2)

        v_xml = col_a.selectbox(
            "Versão XML (Padrão TISS)",
            VERSOES_TISS,
            index=(
                VERSOES_TISS.index(dados_conv.get("versao_xml"))
                if dados_conv and dados_conv.get("versao_xml") in VERSOES_TISS
                else 0
            )
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
#       TELA — CONSULTA PROFISSIONAL (DESIGN MICROSOFT/MV)
# ============================================================
elif menu == "Consulta de Convênios":

    st.markdown("<div class='card'><div class='card-title'>🔎 Consulta de Convênios</div>", unsafe_allow_html=True)

    if not dados_atuais:
        st.info("Nenhum convênio cadastrado.")
        st.stop()

    nomes_conv = sorted([c["nome"] for c in dados_atuais])
    escolha = st.selectbox("Selecione o convênio:", nomes_conv)

    dados = next(c for c in dados_atuais if c["nome"] == escolha)

    # CABEÇALHO PREMIUM
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

    # -------- CARD IDENTIFICAÇÃO --------
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='card-title'>🧾 Dados de Identificação</div>", unsafe_allow_html=True)
    st.markdown(f"""
        <div class='info-line'>Empresa: <span class='value'>{dados.get('empresa','N/A')}</span></div>
        <div class='info-line'>Código: <span class='value'>{dados.get('codigo','N/A')}</span></div>
        <div class='info-line'>Sistema: <span class='value'>{dados.get('sistema_utilizado','N/A')}</span></div>
        <div class='info-line'>Retorno: <span class='value'>{dados.get('prazo_retorno','N/A')}</span></div>
    """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # -------- CARD ACESSO --------
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='card-title'>🔐 Acesso ao Portal</div>", unsafe_allow_html=True)
    st.markdown(f"""
        <div class='info-line'>Portal: <span class='value'>{dados['site']}</span></div>
        <div class='info-line'>Login: <span class='value'>{dados['login']}</span></div>
        <div class='info-line'>Senha: <span class='value'>{dados['senha']}</span></div>
    """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # -------- CARD TÉCNICO --------
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='card-title'>📦 Regras Técnicas</div>", unsafe_allow_html=True)
    st.markdown(f"""
        <div class='info-line'>Prazo Envio: <span class='value'>{dados['envio']}</span></div>
        <div class='info-line'>Validade Guia: <span class='value'>{dados['validade']} dias</span></div>
        <div class='info-line'>Envia XML? <span class='value'>{dados['xml']}</span></div>
        <div class='info-line'>Versão XML: <span class='value'>{dados.get('versao_xml','N/A')}</span></div>
        <div class='info-line'>Exige NF? <span class='value'>{dados['nf']}</span></div>
        <div class='info-line'>Fluxo da Nota: <span class='value'>{dados.get('fluxo_nf','N/A')}</span></div>
    """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # -------- BLOCOS ADICIONAIS --------
    if dados.get("config_gerador"):
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<div class='card-title'>⚙️ Configuração XML</div>", unsafe_allow_html=True)
        st.code(dados["config_gerador"])
        st.markdown("</div>", unsafe_allow_html=True)

    if dados.get("doc_digitalizacao"):
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<div class='card-title'>🗂 Digitalização e Documentação</div>", unsafe_allow_html=True)
        st.info(dados["doc_digitalizacao"])
        st.markdown("</div>", unsafe_allow_html=True)

    
       
    if dados.get("observacoes"):
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<div class='card-title'>⚠️ Observações Críticas</div>", unsafe_allow_html=True)
    
        st.markdown(
            f"""
            <div style="
                background-color: white;
                color: {TEXT_DARK};
                border-left: 4px solid {PRIMARY_COLOR};
                padding: 12px 16px;
                border-radius: 6px;
                font-size: 15px;
                line-height: 1.5;
            ">
                {dados["observacoes"]}
            </div>
            """,
            unsafe_allow_html=True
        )
    
        st.markdown("</div>", unsafe_allow_html=True)



    st.caption("GABMA Consultoria — Visualização Premium")



# ============================================================
#       TELA — VISUALIZAR BANCO COMPLETO
# ============================================================
elif menu == "Visualizar Banco":

    st.markdown("<div class='card'><div class='card-title'>📋 Banco de Dados Completo</div>", unsafe_allow_html=True)

    if dados_atuais:
        st.dataframe(pd.DataFrame(dados_atuais))
    else:
        st.info("Banco vazio.")

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
#  APP.PY — PARTE 4
#  Refinamentos premium do design Microsoft/MV
# ============================================================

# -----------------------------------------
#   CSS Premium Fluent (Microsoft Fluent 2)
# -----------------------------------------
st.markdown(
    f"""
    <style>

        /* ================================ */
        /*   ANIMAÇÕES ESMERALD SOFT       */
        /* ================================ */

        .card {{
            transition: all 0.18s ease-in-out;
        }}
        .card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }}


        /* ================================ */
        /*   HEADER SUPER PREMIUM           */
        /* ================================ */

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


        /* ================================ */
        /*   BOTÕES FLUENT STYLE           */
        /* ================================ */

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

        /* Radio e Select mais elegantes */
        .stSelectbox, .stTextInput, .stTextArea, .stRadio {{
            font-size: 15px!important;
        }}

        /* Ajuste suave no corpo */
        .block-container {{
            padding-top: 0px !important;
        }}

    </style>
    """,
    unsafe_allow_html=True
)


# ---------------------------------------------------
#   HEADER PREMIUM FIXO (substitui título comum)
# ---------------------------------------------------
st.markdown(
    f"""
    <div class="header-premium">
        <span class="header-title">💼 GABMA — Sistema Técnico Corporativo</span>
    </div>
    """,
    unsafe_allow_html=True
)
st.write("")  # espaçamento


# ---------------------------------------------------
#   BOTÃO GLOBAL DE ATUALIZAÇÃO (Topo)
# ---------------------------------------------------
st.sidebar.markdown("### 🔄 Atualização")
if st.sidebar.button("Recarregar Sistema"):
    st.rerun()


# ---------------------------------------------------
#   FOOTER CORPORATIVO GABMA
# ---------------------------------------------------
st.markdown(
    f"""
    <br><br>
    <div style='text-align:center; color:#777; font-size:13px; padding:10px;'>
        © {2026} — GABMA Consultoria · Sistema Técnico de Convênios<br>
        Desenvolvido com design corporativo Microsoft/MV
    </div>
    """,
    unsafe_allow_html=True
)


