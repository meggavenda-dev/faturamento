
# rotinas_module.py
# Módulo de "Rotinas do Setor" — independente, com injeção de dependências

from typing import Callable, Any, List, Tuple
from fpdf import FPDF
import streamlit as st
import pandas as pd
import time
import re

class RotinasModule:
    """
    Injeção de dependências:
      - db_rotinas: instância de GitHubJSON (já criada no app principal)
      - sanitize_text, build_wrapped_lines, _pdf_set_fonts, generate_id, safe_get: funções utilitárias do app
      - primary_color: hex da sua paleta (ex.: #1F497D)
    """
    def __init__(
        self,
        db_rotinas: Any,
        sanitize_text: Callable[[str], str],
        build_wrapped_lines: Callable[[str, FPDF, float, float, float], List[Tuple[str, float]]],
        _pdf_set_fonts: Callable[[FPDF], str],
        generate_id: Callable[[list], int],
        safe_get: Callable[[dict, str, str], str],
        primary_color: str = "#1F497D",
    ):
        self.db = db_rotinas
        self.sanitize_text = sanitize_text
        self.build_wrapped_lines = build_wrapped_lines
        self._pdf_set_fonts = _pdf_set_fonts
        self.generate_id = generate_id
        self.safe_get = safe_get
        self.primary_color = primary_color

    # ---------------------------
    # PDF de UMA rotina
    # ---------------------------
    def gerar_pdf_rotina(self, dados: dict) -> bytes:
        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_margins(15, 12, 15)
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        BLUE = (31, 73, 125)
        GREY_BAR = (230, 230, 230)
        TEXT = (0, 0, 0)
        CONTENT_W = pdf.w - pdf.l_margin - pdf.r_margin

        FONT = self._pdf_set_fonts(pdf)

        def set_font(size=10, bold=False):
            style = "B" if bold else ""
            try:
                pdf.set_font(FONT, style, size)
            except Exception:
                pdf.set_font("Helvetica", style, size)

        def bar_title(texto, top_margin=3, height=8):
            pdf.ln(top_margin)
            pdf.set_fill_color(*GREY_BAR)
            set_font(12, True)
            pdf.cell(0, height, f" {texto.upper()}", ln=1, fill=True)
            pdf.ln(1.5)

        # Título — SOMENTE o nome da rotina
        nome_rot = self.sanitize_text(self.safe_get(dados, "nome")).upper()
        titulo_full = nome_rot if nome_rot else ""

        pdf.set_fill_color(*BLUE)
        pdf.set_text_color(255, 255, 255)
        set_font(18, True)
        pdf.cell(0, 14, titulo_full, ln=1, align="C", fill=True)
        pdf.set_text_color(*TEXT)
        pdf.ln(5)

        # Seção "Descrição"
        bar_title("Descrição")

        descricao = self.safe_get(dados, "descricao")
        left_margin = pdf.l_margin
        width = CONTENT_W
        line_h = 6.6
        padding = 1.8
        bullet_indent = 4.0
        usable_w = width - 2 * padding
        set_font(10, False)

        wrapped_lines = self.build_wrapped_lines(descricao, pdf, usable_w, line_h, bullet_indent=bullet_indent)

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

        # Retorna bytes
        result = pdf.output(dest="S")
        if isinstance(result, str):
            try:
                result = result.encode("latin-1")
            except Exception:
                result = result.encode("latin-1", "ignore")
        return result

    # ---------------------------
    # Página Streamlit
    # ---------------------------
    def page(self):
        rotinas_atuais, _ = self.db.load(force=True)
        rotinas_atuais = list(rotinas_atuais)

        st.markdown(
            f"""
            <div class='card'>
              <div class='card-title'>🗂️ Rotinas do Setor — Cadastro / Edição</div>
            """,
            unsafe_allow_html=True
        )

        opcoes = ["+ Nova Rotina"] + [
            f"{r.get('id')} — {self.safe_get(r, 'nome')}" for r in rotinas_atuais
        ]
        escolha = st.selectbox("Selecione uma rotina para editar:", opcoes)

        if escolha == "+ Nova Rotina":
            rotina_id = None
            dados_rotina = None
        else:
            rotina_id = escolha.split(" — ")[0]
            dados_rotina = next(
                (r for r in rotinas_atuais if str(r.get('id')) == str(rotina_id)),
                None
            )

        st.markdown("</div>", unsafe_allow_html=True)

        form_key = f"form_rotina_{rotina_id}" if rotina_id else "form_rotina_nova"

        with st.form(key=form_key):
            nome = st.text_input("Nome da Rotina", value=self.safe_get(dados_rotina, "nome"))
            descricao = st.text_area(
                "Descrição da Rotina",
                value=self.safe_get(dados_rotina, "descricao"),
                height=300,
                help="Use parágrafos e bullets (•, -, ->). URLs são quebradas corretamente no PDF."
            )

            submit = st.form_submit_button("💾 Salvar Rotina")

            if submit:
                novo_registro = {
                    "nome": nome,
                    "descricao": descricao,
                }

                if rotina_id is None:
                    novo_registro["id"] = self.generate_id(rotinas_atuais)
                    rotinas_atuais.append(novo_registro)
                else:
                    novo_registro["id"] = int(rotina_id)
                    for i, r in enumerate(rotinas_atuais):
                        if str(r.get("id")) == str(rotina_id):
                            rotinas_atuais[i] = novo_registro
                            break

                if self.db.save(rotinas_atuais):
                    st.success(f"✔ Rotina {novo_registro['id']} salva com sucesso!")
                    # limpa caches e estado, mantendo o padrão do app
                    self.db._cache_data = None
                    self.db._cache_sha = None
                    self.db._cache_time = 0.0
                    st.session_state.clear()
                    time.sleep(1)
                    st.rerun()

        # Botão PDF
        if dados_rotina:
            st.download_button(
                "📥 Baixar PDF da Rotina",
                self.gerar_pdf_rotina(dados_rotina),
                file_name=f"Rotina_{self.safe_get(dados_rotina,'nome')}.pdf",
                mime="application/pdf"
            )

        # Visualização do banco
        st.markdown("<div class='card'><div class='card-title'>📋 Banco de Rotinas</div>", unsafe_allow_html=True)
        if rotinas_atuais:
            df = pd.DataFrame(rotinas_atuais)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("⚠️ Nenhuma rotina cadastrada.")
        st.markdown("</div>", unsafe_allow_html=True)
