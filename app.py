import streamlit as st
from fpdf import FPDF
import re

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="GABMA - Gestão de Faturamento", layout="wide")

# --- FUNÇÃO DE EXTRAÇÃO (PARSER) ---
def extrair_dados_manual(texto_manual):
    # Lista de convênios baseada no seu manual fornecido
    convenios_identificados = [
        "ASSEFAZ", "ASTE", "AMIL", "ASFUB", "ASSPUB", "ASPDF", 
        "BENECAP", "BACEN", "CAPESESP", "CASEMBRAPA", "CBMDF", 
        "CONAB", "E-VIDA", "FACEB", "GEAP", "GDF SAÚDE", "IDEAL",
        "INTERMÉDICA", "LIFE EMPRESARIAL", "MEDSENIOR", "PLAN ASSISTE",
        "SAÚDE CAIXA", "SIS SENADO", "CARE PLUS", "BRADESCO", "CASSI", 
        "MEDISERVICE", "POSTAL SAÚDE", "SERPRO", "GAMA SAÚDE", "SULAMÉRICA",
        "TRE", "FASCAL", "UNIVIDA", "TOP LIFE", "TRT", "TRF"
    ]
    
    dados_extraidos = []
    for i, nome in enumerate(convenios_identificados):
        inicio = texto_manual.find(nome + ":")
        if inicio == -1: continue
        
        # Define o fim do bloco buscando o próximo convênio
        fim = len(texto_manual)
        for proximo in convenios_identificados[i+1:]:
            pos_proximo = texto_manual.find(proximo + ":")
            if pos_proximo != -1 and pos_proximo > inicio:
                fim = pos_proximo
                break
        
        bloco = texto_manual[inicio:fim]
        
        # Regex para extrair dados
        site = re.search(r'https?://[^\s]+', bloco)
        validade = re.search(r'Validade.*?(\d+)\s*dias', bloco, re.IGNORECASE)
        envio = re.search(r'Data de envio:\s*(.*?)(?=\.|\n)', bloco)
        
        dados_extraidos.append({
            "convenio": nome,
            "site": site.group(0) if site else "",
            "login": "", # Manual não costuma ter login/senha por segurança
            "senha": "",
            "validade": validade.group(1) if validade else "",
            "envio": envio.group(1) if envio else "",
            "xml": "Sim" if "XML" in bloco.upper() else "Não",
            "nf": "Sim" if ("NOTA FISCAL" in bloco.upper() or "NF" in bloco.upper()) else "Não",
            "texto_completo": bloco.strip()
        })
    return dados_extraidos

# --- FUNÇÃO GERADORA DE PDF ---
def gerar_pdf(dados):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, f"Formulário de Faturamento: {dados['convenio']}", ln=True, align='C')
    pdf.ln(10)
    
    secoes = [
        ("1. Acesso e Portal", f"Site: {dados['site']}\nLogin: {dados['login']}\nSenha: {dados['senha']}\nXML: {dados['xml']}"),
        ("2. Cronograma", f"Envio: {dados['envio']}\nValidade: {dados['validade']} dias"),
        ("3. Nota Fiscal", f"Exige NF: {dados['nf']}"),
        ("4. Observações Extraídas do Manual", dados['texto_completo'])
    ]
    
    for titulo, conteudo in secoes:
        pdf.set_font("Arial", "B", 12)
        pdf.cell(200, 10, titulo, ln=True)
        pdf.set_font("Arial", "", 10)
        pdf.multi_cell(0, 6, conteudo)
        pdf.ln(5)
        
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFACE STREAMLIT ---
st.title("🚀 GABMA - Sistema de Inteligência em Faturamento")
st.markdown("Importe o manual bruto e gere formulários padronizados em PDF.")

aba1, aba2 = st.tabs(["📥 Importar Manual", "📝 Gerenciar Convênios"])

with aba1:
    st.header("Upload de Dados")
    manual_input = st.text_area("Cole aqui o texto do manual de convênios:", height=300)
    if st.button("Processar Manual"):
        if manual_input:
            resultado = extrair_dados_manual(manual_input)
            st.session_state['lista_convenios'] = resultado
            st.success(f"Sucesso! {len(resultado)} convênios identificados.")
        else:
            st.error("Por favor, cole o texto do manual.")

with aba2:
    if 'lista_convenios' in st.session_state:
        lista = st.session_state['lista_convenios']
        nomes = [c['convenio'] for c in lista]
        escolha = st.selectbox("Selecione o convênio para editar/gerar PDF:", nomes)
        
        # Filtra o convênio selecionado
        dados_conv = next(item for item in lista if item["convenio"] == escolha)
        
        # Formulário de edição
        with st.expander(f"Editar Dados de {escolha}", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                dados_conv['site'] = st.text_input("Site", dados_conv['site'])
                dados_conv['login'] = st.text_input("Login")
                dados_conv['senha'] = st.text_input("Senha", type="password")
            with col2:
                dados_conv['envio'] = st.text_input("Data de Envio", dados_conv['envio'])
                dados_conv['validade'] = st.text_input("Validade (Dias)", dados_conv['validade'])
            
            dados_conv['texto_completo'] = st.text_area("Observações do Manual", dados_conv['texto_completo'], height=200)

        # Botão para gerar PDF
        pdf_bytes = gerar_pdf(dados_conv)
        st.download_button(
            label=f"📥 Baixar PDF - {escolha}",
            data=pdf_bytes,
            file_name=f"Faturamento_{escolha}.pdf",
            mime="application/pdf"
        )
    else:
        st.info("Importe um manual na primeira aba para começar.")
