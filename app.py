import streamlit as st
import pandas as pd
import google.generativeai as genai
from io import BytesIO

# --- Configurar clave API ---
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# --- Cargar archivo ---
st.set_page_config(page_title="📊 Asesor Financiero con IA - Fénix Automotriz")
st.title("📊 Asesor Financiero con IA para Fénix Automotriz")
uploaded_file = st.file_uploader("📂 Sube un archivo Excel (.xlsx) con múltiples hojas", type=["xlsx"])

if uploaded_file is not None:
    try:
        excel_data = pd.read_excel(uploaded_file, sheet_name=None)  # leer TODAS las hojas
        sheet_names = list(excel_data.keys())

        st.success(f"Se cargaron {len(sheet_names)} hojas: {', '.join(sheet_names)}")

        # Mostrar vista previa de cada hoja
        for sheet in sheet_names:
            st.subheader(f"📄 Vista previa: {sheet}")
            st.dataframe(excel_data[sheet].head(10))

        # Convertir todas las hojas en texto para análisis
        full_context = ""
        for name, df in excel_data.items():
            full_context += f"Hoja: {name}\n{df.head(100).to_string(index=False)}\n\n"

        # Entrada de pregunta
        st.markdown("### 💬 Pregúntale a la IA sobre estos datos:")
        question = st.text_input("Escribe tu pregunta:")

        if question:
            model = genai.GenerativeModel("gemini-pro")
            prompt = f'''Eres un analista financiero inteligente. Responde en español preguntas del usuario sobre los datos que vienen a continuación.
Datos:
{full_context}

Pregunta: {question}
Responde en lenguaje claro y profesional.'''

            with st.spinner("Pensando..."):
                response = model.generate_content(prompt)
                st.markdown("### 🤖 Respuesta de la IA:")
                st.write(response.text)
    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")
