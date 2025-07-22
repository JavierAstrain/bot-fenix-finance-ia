import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests

# ---------- CONFIGURACIÓN ----------
st.set_page_config(page_title="Bot Fénix Finance IA", page_icon="🤖")

st.markdown("# 🤖 Bot Fénix Finance IA")
st.markdown("Conecta datos financieros desde Google Sheets para control inteligente.")

# ---------- CARGAR CREDENCIALES GOOGLE ----------
creds_dict = st.secrets["GOOGLE_CREDENTIALS"]
creds = Credentials.from_service_account_info(creds_dict)
client = gspread.authorize(creds)

# ---------- CARGAR GOOGLE SHEET ----------
spreadsheet_url = "https://docs.google.com/spreadsheets/d/1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk"
sheet = client.open_by_url(spreadsheet_url).sheet1
data = sheet.get_all_records()
df = pd.DataFrame(data)

# ---------- MOSTRAR TABLA ----------
st.markdown("## 📊 Datos actuales:")
st.dataframe(df)

# ---------- CAJA DE PREGUNTAS ----------
st.markdown("## 🧠 Pregúntame sobre tus datos:")
question = st.text_input("Escribe tu pregunta:")

if question:
    # Convertir los datos del DataFrame en texto
    table_text = df.to_csv(index=False)

    # API Key de OpenRouter
    openrouter_api_key = st.secrets["OPENROUTER_API_KEY"]

    # Llamada a la API de OpenRouter con modelo gratuito
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://chat.openai.com",  # Requerido por OpenRouter
        },
        json={
            "model": "mistralai/mistral-7b-instruct",
            "messages": [
                {"role": "system", "content": "Eres un analista financiero que responde preguntas con base en los datos que te entregaré."},
                {"role": "user", "content": f"Aquí tienes los datos en CSV:\n\n{table_text}"},
                {"role": "user", "content": question}
            ],
            "temperature": 0.3,
        },
    )

    if response.status_code == 200:
        result = response.json()
        answer = result["choices"][0]["message"]["content"]
        st.markdown("### 🤖 Respuesta:")
        st.write(answer)
    else:
        st.error("Ocurrió un error al consultar la API de OpenRouter.")
