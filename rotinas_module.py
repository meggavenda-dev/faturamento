
# rotinas_module.py
# Módulo "Rotinas do Setor" — Cadastro/Edição + PDF premium + Exclusão permanente
# Usa injeção de dependências do app principal para evitar import circular.

from typing import Callable, Any, List, Tuple
from fpdf import FPDF
from PIL import Image
import streamlit as st
import pandas as pd
import time
import re
import io
import os
import base64

# Import do editor
from streamlit_quill import st_quill
# (Opcional) Import do botão de colar imagem — ainda não usado aqui
from streamlit_paste_button import paste_image_button


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


class RotinasModule:
    """
    Rotinas do Setor — módulo desacoplado do app principal.

    Dependências (injeção via __init__):
      - db_rotinas: instância de GitHubJSON
      - sanitize_text: função(str) -> str
      - build_wrapped_lines: função(str, FPDF, float, float, float) -> List[Tuple[str, float]]
      - _pdf_set_fonts: função(FPDF) -> str  (retorna o nome da fonte ativa)
      - generate_id: função(list) -> int
      - safe_get: função(dict, str, default) -> str
      - primary_color: str (hex)
      - setores_opcoes: List[str]
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
        setores_opcoes: List[str] = None,
    ):
        self.db = db_rotinas
        self.sanitize_text = sanitize_text
        self.build_wrapped_lines = build_wrapped_lines
        self._pdf_set_fonts = _pdf_set_fonts
        self.generate_id = generate_id
        self.safe_get = safe_get
        self.primary_color = primary_color
        self.setores_opcoes = list(setores_opcoes or [])

    # ============================================================
    # LIMPEZA DE HTML (igual ao módulo principal)
    # ============================================================
    def _clean_html(self, raw_html: str) -> str:
        """Remove tags HTML e normaliza espaços — compatível com PDF premium."""
        if not raw_html:
            return ""
        cleanr = re.compile('<.*?>|&nbsp;')
        cleantext = re.sub(cleanr, ' ', raw_html)
        return re.sub(r' +', ' ', cleantext).strip()

    # ============================================================
    # PDF PREMIUM DA ROTINA
    # ============================================================
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

        def bar_title(texto: str, top_margin: float = 3.0, height: float = 8.0):
            pdf.ln(top_margin)
            pdf.set_fill_color(*GREY_BAR)
            set_font(12, True)
            pdf.cell(0, height, f" {texto.upper()}", ln=1, fill=True)
            pdf.ln(1.5)

        # -------- CABEÇALHO --------
        nome_rot = self.sanitize_text(self.safe_get(dados, "nome")).upper()
        pdf.set_fill_color(*BLUE)
        pdf.set_text_color(255, 255, 255)
        set_font(18, True)
        pdf.cell(0, 14, nome_rot or "ROTINA", ln=1, align="C", fill=True)
        pdf.set_text_color(*TEXT)
        pdf.ln(5)

        setor_val = self.sanitize_text(self.safe_get(dados, "setor"))
        if setor_val:
            pdf.set_text_color(80, 80, 80)
            set_font(11, False)
            pdf.cell(0, 7, f"Setor: {setor_val}", ln=1, align="C")
            pdf.set_text_color(*TEXT)
            pdf.ln(2)

        # -------- DESCRIÇÃO --------
        bar_title("Descrição")

        descricao_raw = self.safe_get(dados, "descricao")
        # Extrai imagens antes de limpar HTML
        descricao_with_markers, desc_images = extract_images_from_html(descricao_raw)
        descricao = self._clean_html(descricao_with_markers)

        width = CONTENT_W
        line_h = 6.6
        padding = 1.8
        bullet_indent = 4.0
        usable_w = width - 2 * padding

        set_font(10, False)

        wrapped_lines = self.build_wrapped_lines(
            descricao, pdf, usable_w, line_h, bullet_indent=bullet_indent
        )

        # Renderiza texto e imagens
        i = 0
        img_idx = 0
        while i < len(wrapped_lines):
            # Verifica se a linha atual contém marcador de imagem
            if i < len(wrapped_lines) and "[IMAGEM]" in wrapped_lines[i][0]:
                # Adiciona imagem se houver
                if img_idx < len(desc_images):
                    img = desc_images[img_idx]
                    # Salva imagem temporariamente
                    temp_img_path = f"/tmp/temp_rot_img_{img_idx}.png"
                    img.save(temp_img_path, "PNG")

                    # Calcula dimensões para caber na largura disponível
                    img_width = CONTENT_W - 10  # margem de 5mm de cada lado
                    aspect_ratio = img.height / img.width
                    img_height = img_width * aspect_ratio

                    # Verifica se cabe na página
                    y_curr = pdf.get_y()
                    if y_curr + img_height > pdf.page_break_trigger:
                        pdf.add_page()
                        set_font(10, False)
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
                i += 1
                continue

            y_top = pdf.get_y()
            space = pdf.page_break_trigger - y_top
            avail_h = max(0.0, space - 2 * padding - 0.5)
            lines_per_page = int(avail_h // line_h) if avail_h > 0 else 0
            if lines_per_page <= 0:
                pdf.add_page()
                set_font(10, False)
                continue

            end = min(len(wrapped_lines), i + lines_per_page)
            slice_lines = wrapped_lines[i:end]

            # Filtra linhas com marcador de imagem
            slice_lines = [(txt, ind) for (txt, ind) in slice_lines if "[IMAGEM]" not in txt]
            if not slice_lines:
                i = end
                continue

            box_h = 2 * padding + len(slice_lines) * line_h
            pdf.rect(pdf.l_margin, y_top, width, box_h)

            x_text_base = pdf.l_margin + padding
            y_text = y_top + padding

            for (ln_text, indent_mm) in slice_lines:
                pdf.set_xy(x_text_base + indent_mm, y_text)
                pdf.cell(usable_w - indent_mm, line_h, ln_text)
                y_text += line_h

            pdf.set_y(y_top + box_h)
            i = end

        # fpdf2 retorna bytearray, converter para bytes
        return bytes(pdf.output())

    # ============================================================
    # PÁGINA DO MÓDULO (COM EDITOR QUILL)
    # ============================================================
    def page(self):
        try:
            rotinas_atuais, _ = self.db.load(force=True)
        except Exception:
            rotinas_atuais = []

        if not isinstance(rotinas_atuais, list):
            rotinas_atuais = []
        rotinas_atuais = list(rotinas_atuais)

        st.markdown(
            "<div class='card'><div class='card-title'>🗂️ Rotinas do Setor — Cadastro / Edição</div>",
            unsafe_allow_html=True,
        )

        opcoes = ["+ Nova Rotina"] + [
            f"{r.get('id')} — {self.safe_get(r, 'nome', 'Sem Nome')}" for r in rotinas_atuais
        ]

        escolha = st.selectbox("Selecione uma rotina para editar:", opcoes)

        # Garantimos que dados_rotina seja ao menos um dict vazio
        if escolha == "+ Nova Rotina":
            rotina_id = "novo"
            dados_rotina = {}
        else:
            rotina_id = escolha.split(" — ")[0]
            dados_rotina = next(
                (r for r in rotinas_atuais if str(r.get("id")) == str(rotina_id)),
                {}
            )

        st.markdown("</div>", unsafe_allow_html=True)

        # ============================================================
        # FORMULÁRIO PRINCIPAL
        # ============================================================
        st.markdown("### Detalhes da Rotina")

        nome = st.text_input("Nome da Rotina", value=self.safe_get(dados_rotina, "nome"))

        setor_atual = self.safe_get(dados_rotina, "setor")
        if self.setores_opcoes:
            if setor_atual not in self.setores_opcoes:
                setor_atual = self.setores_opcoes[0]
            idx_setor = (
                self.setores_opcoes.index(setor_atual)
                if setor_atual in self.setores_opcoes
                else 0
            )
            setor = st.selectbox("Setor", self.setores_opcoes, index=idx_setor)
        else:
            setor = st.text_input("Setor", value=setor_atual or "")

        # ============================================================
        # 🖋️ EDITOR QUILL (mínimo compatível + HTML)
        # ============================================================
        st.markdown("##### 🖋️ Descrição Detalhada da Rotina")

        # Garante string (nunca None)
        desc_inicial = str(self.safe_get(dados_rotina, "descricao", ""))

        descricao_html = st_quill(
            value=desc_inicial,
            key=f"quill_editor_rotina_{rotina_id}",  # Key única por rotina
            placeholder="Digite o passo a passo completo da rotina...",
            html=True,  # >>> retorna HTML string (compatível com PDF)
            # NÃO usar theme/modules/formats em versões antigas do streamlit-quill
        )

        # ============================================================
        # SALVAR
        # ============================================================
        if st.button("💾 Salvar Rotina", use_container_width=True):
            if not nome:
                st.error("O nome da rotina é obrigatório.")
            else:
                # Se id for "novo", geramos um novo; senão mantemos o original
                id_final = self.generate_id(rotinas_atuais) if rotina_id == "novo" else int(rotina_id)

                novo_registro = {
                    "id": id_final,
                    "nome": nome,
                    "setor": setor,
                    "descricao": descricao_html,  # HTML salvo no JSON
                }

                if rotina_id == "novo":
                    rotinas_atuais.append(novo_registro)
                else:
                    for i, r in enumerate(rotinas_atuais):
                        if str(r.get("id")) == str(rotina_id):
                            rotinas_atuais[i] = novo_registro
                            break

                if self.db.save(rotinas_atuais):
                    st.success("✔ Rotina salva com sucesso!")
                    self.db._cache_data = None
                    time.sleep(1)
                    st.rerun()

        # ============================================================
        # DOWNLOAD PDF
        # ============================================================
        if dados_rotina:
            try:
                pdf_bytes = self.gerar_pdf_rotina(dados_rotina)

                fname = (
                    f"Rotina_{self.safe_get(dados_rotina,'setor')}_"
                    f"{self.safe_get(dados_rotina,'nome')}.pdf"
                )
                fname = re.sub(r'[\\/:*?"<>|]+', "_", fname)[:120]

                st.download_button(
                    label="📥 Baixar PDF da Rotina",
                    data=pdf_bytes,
                    file_name=fname,
                    mime="application/pdf",
                    key=f"dl_pdf_rotina_{self.safe_get(dados_rotina, 'id')}",
                )

            except Exception as e:
                st.error("Falha ao preparar o PDF para download.")
                st.exception(e)

            # ============================================================
            # EXCLUSÃO PERMANENTE
            # ============================================================
            rotina_id_str = str(dados_rotina.get("id") or "")

            with st.expander("🗑️ Excluir rotina (permanente)", expanded=False):
                st.warning(
                    "Esta ação **não pode ser desfeita**. Para confirmar, "
                    f"digite o **ID {rotina_id_str}** abaixo.",
                    icon="⚠️",
                )

                confirm_val = st.text_input(
                    f"Confirmação: digite **{rotina_id_str}**",
                    key=f"confirm_del_rot_{rotina_id_str}",
                )

                can_delete = confirm_val.strip() == rotina_id_str and bool(rotina_id_str)

                if st.button(
                    "Excluir rotina **permanentemente**",
                    type="primary",
                    disabled=not can_delete,
                ):
                    try:
                        def _update(data):
                            return [
                                r for r in (data or [])
                                if str(r.get("id")) != rotina_id_str
                            ]

                        self.db.update(_update)

                        st.success(f"✔ Rotina {rotina_id_str} excluída com sucesso!")

                        self.db._cache_data = None
                        self.db._cache_sha = None
                        self.db._cache_time = 0.0
                        st.session_state.clear()
                        time.sleep(1)
                        st.rerun()

                    except Exception as e:
                        st.error(f"Falha ao excluir rotina {rotina_id_str}: {e}")

        # ============================================================
        # VISUALIZAÇÃO DO BANCO DE ROTINAS
        # ============================================================
        st.markdown(
            "<div class='card'><div class='card-title'>📋 Banco de Rotinas</div>",
            unsafe_allow_html=True,
        )

        if rotinas_atuais:
            df = pd.DataFrame(rotinas_atuais)
            preferidas = ["id", "setor", "nome", "descricao"]
            col_order = (
                [c for c in preferidas if c in df.columns]
                + [c for c in df.columns if c not in preferidas]
            )
            df = df[col_order]
            st.dataframe(df, use_container_width=True)
        else:
            st.info("⚠️ Nenhuma rotina cadastrada.")

        st.markdown("</div>", unsafe_allow_html=True)
