import streamlit as st
import pandas as pd
import gspread
import json
import requests
from gspread.auth import service_account_from_dict

# --- CARGA CREDENCIALES DESDE SECRETS ---
creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
client_gs = service_account_from_dict(creds_dict, scopes=scope)

# --- CONEXIÓN A GOOGLE SHEET ---
spreadsheet_url = "https://docs.google.com/spreadsheets/d/1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk/edit?gid=0#gid=0"
try:
    sheet = client_gs.open_by_url(spreadsheet_url).sheet1
except Exception as e:
    st.error("❌ No se pudo abrir la hoja. Revisa permisos y credenciales.")
    st.exception(e)
    st.stop()

# --- LECTURA DE DATOS ---
data = sheet.get_all_values()
df = pd.DataFrame(data[1:], columns=data[0])

# --- CONVERSIÓN DE TIPOS ---
df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
df["Monto Facturado"] = pd.to_numeric(df["Monto Facturado"], errors="coerce")

# --- INTERFAZ STREAMLIT ---
st.title("🤖 Bot Fénix Finance IA")
st.write("Haz preguntas en lenguaje natural sobre tu información financiera.")
st.subheader("📊 Vista previa de la planilla:")
st.dataframe(df.head(10))

# --- PREGUNTA DEL USUARIO ---
st.subheader("💬 ¿Qué deseas saber?")
pregunta = st.text_input("Ej: ¿Cuáles fueron las ventas del año 2025?")

if pregunta:
    # --- CONTEXTO PARA LA IA ---
    preview = df.head(20).to_string(index=False)
    contexto = f"""Estos son datos financieros (primeras filas):

{preview}

Ahora responde esta pregunta de forma clara y concreta en español:

{pregunta}
"""

    headers = {
        "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "openai/gpt-3.5-turbo",
        "messages": [{"role": "user", "content": contexto}],
        "temperature": 0.3
    }

    with st.spinner("Consultando IA..."):
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        if response.status_code == 200:
            respuesta = response.json()["choices"][0]["message"]["content"]
            st.success("🤖 Respuesta:")
            st.write(respuesta)
        else:
            st.error(f"Error al consultar OpenRouter ({response.status_code}):")
            st.text(response.text)
