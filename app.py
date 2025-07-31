
import streamlit as st
import pandas as pd
import os
import google.generativeai as genai

st.set_page_config(page_title="Asesor Financiero IA - Fénix", layout="wide")
st.title("📊 Asesor Financiero con IA para Fénix Automotriz")

# Carga de archivo Excel
uploaded_file = st.file_uploader("📁 Sube un archivo Excel (.xlsx) con múltiples hojas", type=["xlsx"])

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    sheet_names = xls.sheet_names
    selected_sheet = st.selectbox("🗂 Selecciona una hoja para analizar", sheet_names)
    df = pd.read_excel(xls, sheet_name=selected_sheet)
    df.columns = df.columns.str.strip()

    st.subheader("📌 Vista previa de los datos:")
    st.dataframe(df.head(10))

    # Configurar Gemini
    genai.configure(api_key=st.secrets["GOOGLE_GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-pro")

    # Preparar contexto
    context_columns = ", ".join(df.columns)
    context = f"Actúa como un asesor financiero experto. Estás analizando una hoja llamada '{selected_sheet}' con las siguientes columnas: {context_columns}. El usuario te hará preguntas relacionadas con los datos. Responde de forma clara, precisa y profesional."

    st.divider()
    st.subheader("💬 Pregúntale a la IA sobre estos datos:")
    user_question = st.text_input("Escribe tu pregunta:")

    if user_question:
        preview = df.head(30).to_markdown(index=False)
        full_prompt = f"{context}\n\nDatos:\n{preview}\n\nPregunta del usuario: {user_question}"
        with st.spinner("Pensando..."):
            response = model.generate_content(full_prompt)
            st.success(response.text)
else:
    st.info("🔄 Por favor, sube un archivo Excel para comenzar.")

