import streamlit as st
import gspread
import json
import pandas as pd
import openai
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Fénix Finance Bot", layout="centered")

st.title("🤖 Bot Fénix Finance IA")
st.write("Conecta datos financieros desde Google Sheets para control inteligente.")

spreadsheet_url = "https://docs.google.com/spreadsheets/d/1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk/edit#gid=0"
credentials_json = st.secrets["GOOGLE_CREDENTIALS"]
creds_dict = json.loads(credentials_json)

scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)

client = gspread.authorize(credentials)
sheet = client.open_by_url(spreadsheet_url).sheet1
data = sheet.get_all_records()

df = pd.DataFrame(data)

if not df.empty:
    st.subheader("📊 Datos actuales:")
    st.dataframe(df)
else:
    st.info("No hay datos aún en la hoja.")

# 🔍 Zona de preguntas con GPT
st.subheader("❓ Hazle una pregunta a los datos")

user_question = st.text_input("Escribe tu pregunta (ej: ¿Cuánto se facturó en total?)")

if user_question:
    # Enviar a GPT
    openai.api_key = st.secrets["OPENAI_API_KEY"]

    # Convertir DataFrame a tabla Markdown para mejor análisis
    table_text = df.to_markdown(index=False)

    system_prompt = f"""Eres un asistente financiero. Responde preguntas basadas en la siguiente tabla de datos:

{table_text}

Responde en español de forma breve, clara y basada solo en los datos. Usa cálculos si es necesario."""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_question}
        ],
        temperature=0.3
    )

    st.markdown("**💬 Respuesta:**")
    st.success(response.choices[0].message.content)
