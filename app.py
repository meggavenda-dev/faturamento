
import streamlit as st
import requests
import base64
import json
import re
from fpdf import FPDF
import os
import pandas as pd

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
#     FUNÇÕES DO GITHUB (CRUD JSON)
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

# -----------------------------------------
#     GERADOR DE PDF — LAYOUT PREMIUM
# -----------------------------------------

def gerar_pdf(dados):
    pdf = FPDF()
    pdf.add_page()

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
        pdf.set_font("Helvetica", "", 12)
        fonte_principal = "Helvetica"
        estilo_b = "B"

    pdf.set_fill_color(31, 73, 125)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font(fonte_principal, estilo_b, 16)
    pdf.cell(0, 15, f"GUIA TÉCNICA: {dados['nome'].upper()}", ln=True, align='C', fill=True)
    pdf.ln(5)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font(fonte_principal, estilo_b, 11)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(0, 8, " 1. DADOS DE IDENTIFICAÇÃO E ACESSO", ln=True, fill=True)

    pdf.set_font(fonte_principal, "", 10)
    pdf.ln(2)
    pdf.write(7, f"Empresa: {dados.get('empresa', 'N/A')} | Código: {dados.get('codigo', 'N/A')}\n")
    pdf.write(7, f"Portal: {dados['site']}\n")
    pdf.write(7, f"Login: {dados['login']}  |  Senha: {dados['senha']}\n")
    pdf.write(7, f"Sistema: {dados.get('sistema_utilizado', 'N/A')} | Retorno: {dados.get('prazo_retorno', 'N/A')}\n")
    pdf.ln(5)

    pdf.set_font(fonte_principal, estilo_b, 11)
    pdf.set_fill_color(230, 230, 230)
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
    pdf.cell(25, 8, f"{dados['xml']} / {dados.get('versao_xml', '-')}", 1, 0, 'C')
    pdf.cell(25, 8, dados['nf'], 1, 0, 'C')
    pdf.cell(60, 8, dados.get('fluxo_nf', 'N/A')[:35], 1, 1, 'C')
    pdf.ln(5)

    def bloco(titulo, conteudo):
        if conteudo:
            pdf.set_font(fonte_principal, estilo_b, 11)
            pdf.set_fill_color(240, 240, 240)
            pdf.cell(0, 7, f" {titulo}", ln=True, fill=True)

            pdf.set_font(fonte_principal, "", 9)
            pdf.multi_cell(0, 5, conteudo, border=1)
            pdf.ln(3)

    bloco("CONFIGURAÇÃO DO GERADOR (XML)", dados.get("config_gerador", ""))
    bloco("DIGITALIZAÇÃO E DOCUMENTAÇÃO", dados.get("doc_digitalizacao", ""))
    bloco("OBSERVAÇÕES CRÍTICAS", dados["observacoes"])

    pdf.set_y(-20)
    pdf.set_font(fonte_principal, "", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 10, "GABMA Consultoria - Gestão de Faturamento Médico", align='C')

    return bytes(pdf.output())

# -----------------------------------------
#       INTERFACE PRINCIPAL
# -----------------------------------------
st.set_page_config(page_title="GABMA System", layout="wide")
st.title("💼 Sistema de Gestão GABMA")

dados_atuais, sha_atual = buscar_dados_github()

menu = st.sidebar.radio("Navegação", [
    "Cadastrar / Editar",
    "Consulta de Convênios",
    "Visualizar Banco"
])

# -----------------------------------------
#       CADASTRAR / EDITAR
# -----------------------------------------
if menu == "Cadastrar / Editar":
    st.header("📝 Cadastro de Convênio")

    nomes = ["+ Novo Convênio"] + sorted([c["nome"] for c in dados_atuais])
    escolha = st.selectbox("Selecione um convênio:", nomes)

    dados_conv = next((c for c in dados_atuais if c["nome"] == escolha), None)

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

        with col1:
            nome = st.text_input("Nome do Convênio", value=dados_conv["nome"] if dados_conv else "")
            codigo = st.text_input("Código", value=dados_conv.get("codigo", "") if dados_conv else "")
            empresa = st.text_input("Empresa Faturamento", value=dados_conv.get("empresa", "") if dados_conv else "")
            sistema = st.selectbox("Sistema", ["Orizon", "Benner", "Maida", "Facil", "Visual TISS", "Próprio"])

        with col2:
            site = st.text_input("Site/Portal", value=dados_conv["site"] if dados_conv else "")
            login = st.text_input("Login", value=dados_conv["login"] if dados_conv else "")
            senha = st.text_input("Senha", value=dados_conv["senha"] if dados_conv else "")
            retorno = st.text_input("Prazo Retorno", value=dados_conv.get("prazo_retorno", "") if dados_conv else "")

        with col3:
            envio = st.text_input("Prazo Envio", value=dados_conv["envio"] if dados_conv else "")
            validade = st.text_input("Validade Guia", value=dados_conv["validade"] if dados_conv else "")
            xml = st.radio("Envia XML?", ["Sim", "Não"], index=0 if not dados_conv or dados_conv["xml"] == "Sim" else 1)
            nf = st.radio("Exige NF?", ["Sim", "Não"], index=0 if not dados_conv or dados_conv["nf"] == "Sim" else 1)

        st.divider()
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

        fluxo_nf = col_b.selectbox("Fluxo Nota", [
            "Envia XML sem nota",
            "Envia NF junto com o lote"
        ])

        config_gerador = st.text_area("Configuração Gerador XML", value=dados_conv.get("config_gerador", "") if dados_conv else "")
        doc_dig = st.text_area("Digitalização e Documentação", value=dados_conv.get("doc_digitalizacao", "") if dados_conv else "")
        obs = st.text_area("Observações Críticas", value=dados_conv["observacoes"] if dados_conv else "")

        if st.form_submit_button("💾 Salvar Dados"):
            novo = {
                "nome": nome, "codigo": codigo, "empresa": empresa, "sistema_utilizado": sistema,
                "site": site, "login": login, "senha": senha, "prazo_retorno": retorno,
                "envio": envio, "validade": validade, "nf": nf, "fluxo_nf": fluxo_nf,
                "xml": xml, "versao_xml": v_xml, "config_gerador": config_gerador,
                "doc_digitalizacao": doc_dig, "observacoes": obs
            }

            if escolha == "+ Novo Convênio":
                dados_atuais.append(novo)
            else:
                index = next(i for i, c in enumerate(dados_atuais) if c["nome"] == escolha)
                dados_atuais[index] = novo

            if salvar_dados_github(dados_atuais, sha_atual):
                st.success("Dados salvos com sucesso!")
                st.rerun()

    if dados_conv:
        st.divider()
        st.download_button(
            "📥 Baixar PDF do Convênio",
            gerar_pdf(dados_conv),
            f"GABMA_{escolha}.pdf",
            "application/pdf"
        )

# -----------------------------------------
#       CONSULTA DE CONVÊNIOS
# -----------------------------------------
elif menu == "Consulta de Convênios":
    st.header("📚 Consulta de Convênios")

    if not dados_atuais:
        st.info("Nenhum convênio cadastrado.")
        st.stop()

    nomes_conv = sorted([c["nome"] for c in dados_atuais])
    escolha = st.selectbox("Selecione o convênio:", nomes_conv)

    dados = next(c for c in dados_atuais if c["nome"] == escolha)

    st.markdown("---")

    st.markdown(
        f"""
        <div style='padding: 20px; border-radius: 12px; 
                     background-color: #1f497d; color: white; 
                     text-align:center; font-size:26px;'>
            {dados['nome'].upper()}
        </div>
        """,
        unsafe_allow_html=True
    )

    st.subheader("🧾 Dados de Identificação")
    st.info(f"""
**Empresa:** {dados.get('empresa', 'N/A')}  
**Código:** {dados.get('codigo', 'N/A')}  
**Sistema:** {dados.get('sistema_utilizado', 'N/A')}  
**Retorno:** {dados.get('prazo_retorno', 'N/A')}
""")

    st.subheader("🔐 Acesso ao Portal")
    st.success(f"""
**Portal:** {dados['site']}  
**Login:** {dados['login']}  
**Senha:** {dados['senha']}
""")

    st.subheader("📦 Regras Técnicas")
    st.write(f"""
**Prazo Envio:** {dados["envio"]}  
**Validade da Guia:** {dados["validade"]} dias  
**Envia XML?** {dados["xml"]}  
**Versão XML:** {dados.get("versao_xml", "N/A")}  
**Exige NF?** {dados["nf"]}  
**Fluxo da Nota:** {dados.get("fluxo_nf", "N/A")}
""")

    if dados.get("config_gerador"):
        st.subheader("⚙️ Configuração do Gerador XML")
        st.code(dados["config_gerador"])

    if dados.get("doc_digitalizacao"):
        st.subheader("🗂 Digitalização e Documentação")
        st.info(dados["doc_digitalizacao"])

    if dados.get("observacoes"):
        st.subheader("⚠️ Observações Críticas")
        st.warning(dados["observacoes"])

    st.markdown("---")
    st.caption("GABMA Consultoria — Consulta de Convênios")

# -----------------------------------------
#       VISUALIZAR BANCO
# -----------------------------------------
elif menu == "Visualizar Banco":
    st.header("📋 Cadastro Geral")
    if dados_atuais:
        st.dataframe(pd.DataFrame(dados_atuais))
    else:
        st.info("Banco vazio.")
