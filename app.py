api = st.secrets["openrouter"]["OPENROUTER_API_KEY"]
st.write("🔑 Clave cargada:", api[:10] + "..." )  # solo muestra principio
import streamlit as st
import pandas as pd
import gspread
import json
import requests
from google.oauth2.service_account import Credentials

# --- CARGA CREDENCIALES GOOGLE DESDE SECRETS ---
creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
scope = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(creds)

# --- URL DE LA HOJA ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk"

try:
    sheet = client.open_by_url(SHEET_URL).sheet1
    data = sheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df["Monto Facturado"] = pd.to_numeric(df["Monto Facturado"], errors="coerce")

    # --- UI STREAMLIT ---
    st.title("🤖 Bot Fénix Finance IA")
    st.write("Haz preguntas en lenguaje natural sobre tu información financiera.")
    st.subheader("📊 Vista previa:")
    st.dataframe(df.head(10))

    st.subheader("💬 ¿Qué deseas saber?")
    pregunta = st.text_input("Ej: ¿Cuáles fueron las ventas del año 2025?")

    if pregunta:
        contexto = f"""Estos son datos financieros (primeras filas):

{df.head(20).to_string(index=False)}

Ahora responde esta pregunta de forma clara y concreta en español:

{pregunta}
"""
        headers = {
            "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "openchat/openchat-7b",
            "messages": [{"role": "user", "content": contexto}],
            "temperature": 0.3
        }

        try:
            with st.spinner("Consultando IA..."):
                response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
                if response.status_code == 200:
                    content = response.json()["choices"][0]["message"]["content"]
                    st.success("🤖 Respuesta:")
                    st.write(content)
                else:
                    st.error(f"❌ Error al consultar OpenRouter: {response.status_code}")
                    st.text(response.text)
        except Exception as e:
            st.error("❌ Falló la conexión con OpenRouter.")
            st.exception(e)

except Exception as e:
    st.error("❌ No se pudo cargar la hoja de cálculo.")
    st.exception(e)
