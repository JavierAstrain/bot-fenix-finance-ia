import streamlit as st
import pandas as pd
import gspread
import json
import requests
from google.oauth2.service_account import Credentials

# --- CARGA CREDENCIALES DESDE SECRETS ---
creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
scope = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
client_gs = gspread.authorize(creds)

# --- CARGA DATA DESDE GOOGLE SHEET ---
spreadsheet_url = "https://docs.google.com/spreadsheets/d/1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk"
try:
    sheet = client_gs.open_by_url(spreadsheet_url).sheet1
    data = sheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])

    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df["Monto Facturado"] = pd.to_numeric(df["Monto Facturado"], errors="coerce")

    # --- INTERFAZ ---
    st.title("🤖 Bot Fénix Finance IA")
    st.write("Haz preguntas en lenguaje natural sobre tu información financiera.")
    st.subheader("📊 Vista previa:")
    st.dataframe(df.head(10))

    st.subheader("💬 ¿Qué deseas saber?")
    pregunta = st.text_input("Ej: ¿Cuáles fueron las ventas del año 2025?")

    if pregunta:
        preview = df.head(20).to_string(index=False)
        contexto = f"""Estos son datos financieros (primeras filas):

{preview}

Ahora responde esta pregunta de forma clara y concreta en español:

import requests

headers = {
    "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}",
    "Content-Type": "application/json"
}
payload = {
    "model": "openai/gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hola"}],
    "temperature": 0.3
}

resp = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers=headers,
    json=payload
)
st.write("Status:", resp.status_code)
st.write("Response:", resp.text)


except Exception as e:
    st.error("\u274c No se pudo abrir la hoja. Revisa permisos y credenciales.")
    st.exception(e)

