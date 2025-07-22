import streamlit as st
import pandas as pd
import json
import os
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI

# --- Configurar página ---
st.set_page_config(page_title="Bot Fénix Finance IA", layout="centered")

st.markdown("## 😎 Bot Fénix Finance IA")
st.markdown("Conecta datos financieros desde Google Sheets para control inteligente.")
st.markdown("### 📊 Datos actuales:")

# --- Autenticación Google Sheets ---
google_credentials = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
credentials = Credentials.from_service_account_info(google_credentials, scopes=scopes)

client_gspread = gspread.authorize(credentials)

# --- Leer datos de Google Sheet ---
spreadsheet_url = "https://docs.google.com/spreadsheets/d/1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk/edit#gid=0"
sheet = client_gspread.open_by_url(spreadsheet_url).sheet1
data = sheet.get_all_records()
df = pd.DataFrame(data)

st.dataframe(df)

# --- Chatbot financiero ---
st.markdown("---")
st.markdown("### 🤖 Pregúntame sobre tus datos:")

user_question = st.text_input("Escribe tu pregunta:", placeholder="¿Cuál es el monto total facturado?")

if user_question:
    # --- Preparar mensaje para el modelo ---
    prompt = f"""Los siguientes son datos financieros en formato tabla:

{df.to_markdown(index=False)}

Responde a la siguiente pregunta de forma clara y precisa:
{user_question}
"""

    # --- Cliente OpenAI (nuevo SDK v1.x) ---
    os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
    client_openai = OpenAI()

    with st.spinner("Analizando con inteligencia artificial..."):
        response = client_openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Eres un asistente experto en análisis financiero."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )

        answer = response.choices[0].message.content
        st.success("✅ Respuesta:")
        st.markdown(answer)
