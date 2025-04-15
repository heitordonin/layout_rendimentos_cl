import streamlit as st
import pandas as pd
import re
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="Gerador de CSV Carnê-Leão", layout="centered")
st.title("📄 Gerador de CSV para o Carnê-Leão - Declara Psi")
st.markdown("Envie o arquivo de Excel com os rendimentos a partir da linha 9. As colunas devem estar entre B e F, conforme o modelo padronizado.")

uploaded_file = st.file_uploader("Escolha o arquivo XLSX", type=["xlsx"])

# Função de validação formal de CPF
def cpf_valido(cpf):
    if not cpf or len(cpf) != 11 or not cpf.isdigit():
        return False
    if cpf == cpf[0] * 11:
        return False
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    d1 = (soma * 10 % 11) % 10
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    d2 = (soma * 10 % 11) % 10
    return cpf[-2:] == f"{d1}{d2}"

if uploaded_file:
    df = pd.read_excel(
        uploaded_file,
        skiprows=8,
        usecols="B:F",
        header=None,
        names=["Data", "CPF_Titular", "CPF_Beneficiario", "Descricao", "Valor"],
        dtype=str
    )

    def limpar_cpf(cpf):
        if pd.isna(cpf):
            return ''
        return re.sub(r'\D', '', cpf)

    df["CPF_Titular"] = df["CPF_Titular"].apply(limpar_cpf)
    df["CPF_Beneficiario"] = df["CPF_Beneficiario"].apply(limpar_cpf)
    df["CPF_Beneficiario"] = df["CPF_Beneficiario"].replace('', pd.NA)
    df["CPF_Beneficiario"].fillna(df["CPF_Titular"], inplace=True)

    # Validar CPF formalmente
    df["CPF_Titular_Valido"] = df["CPF_Titular"].apply(cpf_valido)
    df["CPF_Beneficiario_Valido"] = df["CPF_Beneficiario"].apply(cpf_valido)

    # Separar inválidos
    df_invalidos = df[~(df["CPF_Titular_Valido"] & df["CPF_Beneficiario_Valido"])]
    df_validos = df[(df["CPF_Titular_Valido"] & df["CPF_Beneficiario_Valido"])]

    if not df_invalidos.empty:
        st.error("⚠️ Foram encontrados CPFs inválidos. As linhas com erro foram excluídas do CSV final.")
        st.markdown("Você pode baixar abaixo o relatório com os dados inválidos para correção.")
        buffer_invalidos = BytesIO()
        df_invalidos.to_excel(buffer_invalidos, index=False, sheet_name="CPFs Inválidos")
        st.download_button(
            label="📥 Baixar relatório de CPFs inválidos",
            data=buffer_invalidos.getvalue(),
            file_name="linhas_invalidas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # Corrigir datas para manter o ano como 2024
    df_validos["Data"] = pd.to_datetime(df_validos["Data"], errors="coerce")
    df_validos = df_validos[df_validos["Data"].notna() & df_validos["CPF_Titular"].notna()]
    df_validos["Data"] = df_validos["Data"].apply(lambda d: d.replace(year=2024).strftime("%d/%m/%Y"))

    dados_csv = []
    for _, row in df_validos.iterrows():
        linha = [
            row["Data"],
            "R01.001.001",
            "255",
            row["Valor"] if pd.notna(row["Valor"]) else '',
            '',
            row["Descricao"],
            "PF",
            row["CPF_Titular"],
            row["CPF_Beneficiario"],
            ''
        ]
        dados_csv.append(linha)

    df_export = pd.DataFrame(dados_csv)

    st.success("Pré-visualização do CSV gerado:")
    st.dataframe(df_export, hide_index=True)

    # Exibir estatísticas
    total_linhas = len(df_export)
    try:
        soma_valores = pd.to_numeric(df_export[3], errors='coerce').sum()
    except:
        soma_valores = 0

    st.markdown(f"**Total de linhas processadas:** {total_linhas}")
    st.markdown(f"**Soma total dos valores:** R$ {soma_valores:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    # Criar arquivo CSV para download com separador ponto e vírgula
    output = BytesIO()
    df_export.to_csv(output, index=False, header=False, sep=';')
    st.download_button(
        label="🔹 Baixar CSV para Carnê-Leão",
        data=output.getvalue(),
        file_name="CSV_Carne_Leao_DeclaraPsi.csv",
        mime="text/csv"
    )