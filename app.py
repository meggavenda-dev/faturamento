import streamlit as st
import requests
import base64
import json
import re
from fpdf import FPDF

# --- CONFIGURAÇÕES DE ACESSO (Secrets) ---
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_OWNER = st.secrets["REPO_OWNER"]
    REPO_NAME = st.secrets["REPO_NAME"]
except:
    st.error("Configure os Secrets (GITHUB_TOKEN, REPO_OWNER, REPO_NAME) no Streamlit Cloud.")
    st.stop()

FILE_PATH = "dados.json"
BRANCH = "main"

# --- FUNÇÕES DA API DO GITHUB ---
def buscar_dados_github():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}?ref={BRANCH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        content = response.json()
        decoded_data = base64.b64decode(content['content']).decode('utf-8')
        return json.loads(decoded_data), content['sha']
    else:
        # Se o arquivo não existir, retorna lista vazia
        return [], None

def salvar_dados_github(novos_dados, sha):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    json_string = json.dumps(novos_dados, indent=4, ensure_ascii=False)
    encoded_content = base64.b64encode(json_string.encode('utf-8')).decode('utf-8')
    
    payload = {
        "message": "Update faturamento via GABMA System",
        "content": encoded_content,
        "branch": BRANCH
    }
    if sha:
        payload["sha"] = sha
        
    response = requests.put(url, headers=headers, json=payload)
    return response.status_code in [200, 201]

# --- INTELIGÊNCIA DE EXTRAÇÃO ---
def extrair_dados_manual(texto_manual):
    # Lista de convênios para busca baseada no seu manual
    convenios_lista = ["ASSEFAZ", "AMIL", "CBMDF", "GDF SAÚDE", "GEAP", "BRADESCO", "SAÚDE CAIXA", "CASSI", "POSTAL SAÚDE", "E-VIDA", "CONAB"]
    dados_extraidos = []
    for i, nome in enumerate(convenios_lista):
        inicio = texto_manual.find(nome + ":")
        if inicio == -1: continue
        fim = len(texto_manual)
        for proximo in convenios_lista[i+1:]:
            pos_proximo = texto_manual.find(proximo + ":")
            if pos_proximo != -1 and pos_proximo > inicio:
                fim = pos_proximo
                break
        bloco = texto_manual[inicio:fim]
        dados_extraidos.append({
            "nome": nome,
            "site": re.search(r'https?://[^\s]+', bloco).group(0) if re.search(r'https?://[^\s]+', bloco) else "",
            "login": "", "senha": "",
            "envio": re.search(r'Data de envio:\s*(.*?)(?=\.|\n)', bloco).group(1) if re.search(r'Data de envio:\s*(.*?)(?=\.|\n)', bloco) else "Ver manual",
            "validade": re.search(r'Validade.*?(\d+)\s*dias', bloco, re.IGNORECASE).group(1) if re.search(r'Validade.*?(\d+)\s*dias', bloco, re.IGNORECASE) else "",
            "xml": "Sim" if "XML" in bloco.upper() else "Não",
            "nf": "Sim" if "NF" in bloco.upper() else "Não",
            "observacoes": bloco.strip()
        })
    return dados_extraidos

# --- GERADOR DE PDF ---
def gerar_pdf(dados):
    # Inicializa o PDF com suporte a UTF-8 (nativo na fpdf2)
    pdf = FPDF()
    pdf.add_page()
    
    # Usamos fontes padrão que suportam acentos (Helvetica/Arial)
    pdf.set_font("Helvetica", "B", 16)
    
    # Cabeçalho Centralizado
    pdf.cell(0, 10, f"Formulário de Faturamento: {dados['nome']}", new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.ln(10)
    
    # Seção 1: Dados de Acesso
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, "1. Acesso e Portal", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    
    info_acesso = (
        f"Site: {dados['site']}\n"
        f"Login: {dados['login']} | Senha: {dados['senha']}\n"
        f"XML: {dados['xml']} | Envio: {dados['envio']}\n"
        f"Validade: {dados['validade']} dias"
    )
    pdf.multi_cell(0, 7, info_acesso)
    pdf.ln(5)
    
    # Seção 2: Regras e Observações
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, "2. Regras Extraídas do Manual", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    
    # O fpdf2 lida bem com UTF-8, mas caso existam caracteres "invisíveis" problemáticos,
    # fazemos uma limpeza leve para garantir a renderização
    obs_texto = dados['observacoes'].replace('\u2013', '-').replace('\u2014', '-')
    
    # Multi_cell para permitir que o texto quebre linhas automaticamente
    pdf.multi_cell(0, 6, obs_texto)
    
    # Gera os bytes do PDF diretamente (dest='S' agora retorna bytes no fpdf2)
    return pdf.output()

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="GABMA System", layout="wide")
st.title("💼 GABMA - Faturamento Inteligente (JSON DB)")

# Carrega dados do GitHub
dados_atuais, sha_atual = buscar_dados_github()

menu = st.sidebar.radio("Navegação", ["Gerenciar Convênios", "Importar Novo Manual"])

if menu == "Importar Novo Manual":
    st.header("📥 Importação em Massa")
    txt = st.text_area("Cole o texto do manual aqui:", height=300)
    if st.button("Processar e Salvar no GitHub"):
        novos = extrair_dados_manual(txt)
        # Mesclar dados novos com antigos
        mapa_existente = {c['nome']: c for c in dados_atuais}
        for n in novos:
            mapa_existente[n['nome']] = n
        
        if salvar_dados_github(list(mapa_existente.values()), sha_atual):
            st.success("JSON atualizado com sucesso no repositório!")
            st.rerun()

elif menu == "Gerenciar Convênios":
    if not dados_atuais:
        st.info("Nenhum convênio cadastrado. Vá em 'Importar Novo Manual'.")
    else:
        nomes = sorted([c['nome'] for c in dados_atuais])
        escolha = st.selectbox("Selecione o convênio para gerenciar:", nomes)
        
        # Busca dados do selecionado
        idx = next(i for i, c in enumerate(dados_atuais) if c['nome'] == escolha)
        dados_conv = dados_atuais[idx]
        
        with st.form("edicao_form"):
            col1, col2 = st.columns(2)
            dados_conv['site'] = col1.text_input("Site", dados_conv['site'])
            dados_conv['login'] = col1.text_input("Login", dados_conv['login'])
            dados_conv['senha'] = col1.text_input("Senha", dados_conv['senha'])
            dados_conv['envio'] = col2.text_input("Data de Envio", dados_conv['envio'])
            dados_conv['validade'] = col2.text_input("Validade (Dias)", dados_conv['validade'])
            dados_conv['observacoes'] = st.text_area("Observações", dados_conv['observacoes'], height=200)
            
            if st.form_submit_button("Salvar Alterações no GitHub"):
                if salvar_dados_github(dados_atuais, sha_atual):
                    st.success("Dados salvos e commitado com sucesso!")
                    st.rerun()
        
        st.divider()
        st.subheader("Gerar Documentação")
        pdf_bytes = gerar_pdf(dados_conv)
        st.download_button(f"📥 Baixar PDF - {escolha}", pdf_bytes, f"Faturamento_{escolha}.pdf", "application/pdf")
