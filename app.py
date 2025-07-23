import streamlit as st
import pandas as pd
import gspread
import json
import requests
from google.oauth2.service_account import Credentials

# --- 1. Cargar credenciales Google desde sección google ---
creds_json = st.secrets["google"]["GOOGLE_CREDENTIALS"]
creds_dict = json.loads(creds_json)
scope = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(creds)

# --- 2. Leer datos Google Sheet ---
spreadsheet_url = "https://docs.google.com/spreadsheets/d/1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk"
try:
    sheet = client.open_by_url(spreadsheet_url).sheet1
    data = sheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0]).assign(
        Fecha=lambda df: pd.to_datetime(df["Fecha"], errors="coerce"),
        **{"Monto Facturado": lambda df: pd.to_numeric(df["Monto Facturado"], errors="coerce")}
    )
except Exception as e:
    st.error("❌ Error al cargar la hoja")
    st.exception(e)
    st.stop()

# --- 3. Interfaz de usuario ---
st.title("🤖 Bot Fénix Finance IA")
st.subheader("📊 Vista previa:")
st.dataframe(df.head(10))

st.subheader("💬 ¿Qué deseas saber?")
pregunta = st.text_input("Ej: ¿Cuáles fueron las ventas del año 2025?")

# --- 4. Si hay pregunta, consultar IA ---
if pregunta:
    preview = df.head(20).to_string(index=False)
    contexto = (
        f"Estos son datos financieros:\n\n{preview}\n\n"
        f"Pregunta: {pregunta}"
    )

    api_key = st.secrets["openrouter"]["OPENROUTER_API_KEY"]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openai/gpt-3.5-turbo",
        "messages": [{"role": "user", "content": contexto}],
        "temperature": 0.3
    }

    with st.spinner("🤖 Consultando IA..."):
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload
        )
    if resp.status_code == 200:
        st.success("🤖 Respuesta:")
        st.write(resp.json()["choices"][0]["message"]["content"])
    else:
        st.error(f"❌ OpenRouter error {resp.status_code}")
        st.write(resp.text)
