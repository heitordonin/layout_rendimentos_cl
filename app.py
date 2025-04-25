import streamlit as st
import pandas as pd
import re
from io import BytesIO
from datetime import datetime
from typing import Tuple

# =============================================================
# Declara Psi ▸ Gerador de CSV para Carnê-Leão (versão modular)
# =============================================================
# • Ajuste adicional: remoção do parâmetro 'theme' do set_page_config
#   para compatibilidade com versões < 1.27 do Streamlit.
# • CPFs com menos de 11 dígitos recebem zeros à esquerda
# • Parametrização de ano-base (sidebar)
# • Toggle de modo escuro (CSS injection)
# =============================================================

# -----------------------------
# 🎨  Temas & identidade visual
# -----------------------------
COR_PRIMARIA = "#0b485a"   # Verde-petróleo Declara Psi
COR_SECUNDARIA = "#01b7e9" # Azul destaque
COR_DESTAQUE = "#e59500"   # Laranja

THEME_DARK_CSS = f"""
<style>
body {{ background-color: {COR_PRIMARIA}; color: #ffffff; }}
header, .st-b8 {{ background: {COR_PRIMARIA}; }}
.stButton>button {{ background:{COR_SECUNDARIA}; color:#ffffff; }}
</style>
"""

# ----------------------
# 🛠️  Funções utilitárias
# ----------------------

def cpf_valido(cpf: str) -> bool:
    """Validação formal de CPF (11 dígitos + DV)"""
    if not cpf or len(cpf) != 11 or not cpf.isdigit() or cpf == cpf[0] * 11:
        return False
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    d1 = (soma * 10 % 11) % 10
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    d2 = (soma * 10 % 11) % 10
    return cpf[-2:] == f"{d1}{d2}"


def limpar_cpf(cpf) -> str:
    """Extrai dígitos e preenche zeros à esquerda para atingir 11 casas"""
    if pd.isna(cpf):
        return ''
    digits = re.sub(r"\D", '', str(cpf))
    if 0 < len(digits) < 11:
        digits = digits.zfill(11)
    return digits


def carregar_planilha(arquivo) -> pd.DataFrame:
    """Lê o XLSX padronizado (dados a partir da linha 9, colunas B:F)"""
    return pd.read_excel(
        arquivo,
        skiprows=8,
        usecols="B:F",
        header=None,
        names=["Data", "CPF_Titular", "CPF_Beneficiario", "Descricao", "Valor"],
        dtype=str,
    )


def separar_validos_invalidos(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    df = df.copy()
    df["CPF_Titular"] = df["CPF_Titular"].apply(limpar_cpf)
    df["CPF_Beneficiario"] = df["CPF_Beneficiario"].apply(limpar_cpf)
    df["CPF_Beneficiario"].replace('', pd.NA, inplace=True)
    df["CPF_Beneficiario"].fillna(df["CPF_Titular"], inplace=True)

    df["CPF_Titular_Valido"] = df["CPF_Titular"].apply(cpf_valido)
    df["CPF_Beneficiario_Valido"] = df["CPF_Beneficiario"].apply(cpf_valido)

    mask_validos = df["CPF_Titular_Valido"] & df["CPF_Beneficiario_Valido"]
    return df[mask_validos].copy(), df[~mask_validos].copy()


def corrigir_datas(df: pd.DataFrame, ano_base: int) -> pd.DataFrame:
    df = df.copy()
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    df = df[df["Data"].notna() & df["CPF_Titular"].notna()]
    df["Data"] = df["Data"].apply(lambda d: d.replace(year=ano_base).strftime("%d/%m/%Y"))
    return df


def construir_dataframe_export(df: pd.DataFrame) -> pd.DataFrame:
    dados = [
        [
            row["Data"],
            "R01.001.001",
            "255",
            row["Valor"] if pd.notna(row["Valor"]) else '',
            '',
            row["Descricao"],
            "PF",
            row["CPF_Titular"],
            row["CPF_Beneficiario"],
            '',
        ]
        for _, row in df.iterrows()
    ]
    return pd.DataFrame(dados)


def download_excel(df: pd.DataFrame, filename: str):
    buffer = BytesIO()
    df.to_excel(buffer, index=False, sheet_name="Dados")
    st.download_button(
        label=f"📥 Baixar {filename}",
        data=buffer.getvalue(),
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# -------------------
# 🚀  Aplicação Streamlit
# -------------------

def main():
    # Removido 'theme' para manter compatibilidade ampla
    st.set_page_config(page_title="Gerador de CSV Carnê-Leão", layout="centered")

    st.sidebar.header("⚙️ Configurações")
    ano_base = st.sidebar.number_input("Ano-base", min_value=2019, max_value=datetime.now().year, step=1, value=2024)
    modo_escuro = st.sidebar.toggle("Modo escuro", value=False)

    if modo_escuro:
        st.markdown(THEME_DARK_CSS, unsafe_allow_html=True)

    st.title("📄 Gerador de CSV para o Carnê-Leão – Declara Psi")
    st.markdown("Envie o arquivo de Excel com os rendimentos a partir da linha 9. As colunas devem estar entre B e F, conforme o modelo padronizado.")

    arquivo = st.file_uploader("Escolha o arquivo XLSX", type=["xlsx"])
    if not arquivo:
        st.stop()

    df_original = carregar_planilha(arquivo)
    df_validos, df_invalidos = separar_validos_invalidos(df_original)
    df_validos = corrigir_datas(df_validos, ano_base)

    if not df_invalidos.empty:
        st.error("⚠️ Foram encontrados CPFs inválidos. As linhas com erro foram excluídas do CSV final.")
        download_excel(df_invalidos, "linhas_invalidas.xlsx")

    df_export = construir_dataframe_export(df_validos)

    st.success("Pré-visualização do CSV gerado:")
    st.dataframe(df_export, hide_index=True, use_container_width=True)

    total_linhas = len(df_export)
    soma_valores = pd.to_numeric(df_export[3], errors='coerce').sum()
    st.markdown(f"**Total de linhas processadas:** {total_linhas}")
    st.markdown(f"**Soma total dos valores:** R$ {soma_valores:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    buffer_csv = BytesIO()
    df_export.to_csv(buffer_csv, index=False, header=False, sep=';')
    st.download_button(
        label="🔹 Baixar CSV para Carnê-Leão",
        data=buffer_csv.getvalue(),
        file_name="CSV_Carne_Leao_DeclaraPsi.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
