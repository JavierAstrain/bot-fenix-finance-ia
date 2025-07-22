import streamlit as st
import pandas as pd
import gspread
import json
import openai
from google.oauth2.service_account import Credentials

# --- CARGAR CREDENCIALES ---
creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
scope = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
client_gs = gspread.authorize(creds)

# --- LEER GOOGLE SHEET ---
spreadsheet_url = "https://docs.google.com/spreadsheets/d/1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk"
sheet = client_gs.open_by_url(spreadsheet_url).sheet1
data = sheet.get_all_values()
df = pd.DataFrame(data[1:], columns=data[0])

# --- LIMPIEZA DE DATOS ---
df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
df["Monto Facturado"] = pd.to_numeric(df["Monto Facturado"], errors="coerce")

# --- MOSTRAR TABLA ---
st.title("🤖 Bot Fénix Finance IA")
st.write("Controlador financiero conversacional basado en tus datos de Google Sheets.")

st.subheader("📊 Tabla actual:")
st.dataframe(df)

# --- IA: CONTEXTO + PREGUNTA ---
st.subheader("💬 Haz una pregunta sobre tu información financiera:")

pregunta = st.text_input("Ejemplo: ¿Cuál fue el monto facturado total en marzo de 2025?")

if pregunta:
    # Convertimos DataFrame a tabla de texto resumida para el prompt
    preview = df.head(15).to_string(index=False)
    contexto = f"""Estos son los datos financieros (solo primeras 15 filas para contexto):
    
{preview}

Pregunta: {pregunta}
Responde de forma clara, en español y basada exclusivamente en los datos entregados arriba."""

    with st.spinner("Pensando..."):
        openai.api_key = st.secrets["OPENROUTER_API_KEY"]
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": contexto}],
            temperature=0.3
        )
        respuesta = response["choices"][0]["message"]["content"]
        st.success("🤖 Respuesta del bot:")
        st.write(respuesta)
