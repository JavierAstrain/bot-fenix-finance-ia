import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# Configurar credenciales desde secrets
creds_dict = st.secrets["GOOGLE_CREDENTIALS"]
creds = Credentials.from_service_account_info(creds_dict)
client = gspread.authorize(creds)

# Leer datos desde Google Sheets
spreadsheet_url = "https://docs.google.com/spreadsheets/d/1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk"
sheet = client.open_by_url(spreadsheet_url).sheet1
data = sheet.get_all_values()

# Convertir a DataFrame
df = pd.DataFrame(data[1:], columns=data[0])

# Convertir columnas necesarias
df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
df["Monto Facturado"] = pd.to_numeric(df["Monto Facturado"], errors="coerce")

# Título
st.title("🤖 Bot Fénix Finance IA")
st.write("Conecta datos financieros desde Google Sheets para control inteligente.")

# Mostrar tabla
st.subheader("📊 Datos actuales:")
st.dataframe(df)

# Pregunta libre
st.subheader("💬 Pregúntame sobre tus datos:")
pregunta = st.text_input("Escribe tu pregunta:")

if pregunta:
    if "ventas" in pregunta.lower() and "2025" in pregunta:
        total_ventas = df[df["Fecha"].dt.year == 2025]["Monto Facturado"].sum()
        st.success(f"✅ Las ventas totales del año 2025 fueron: ${total_ventas:,.0f}")
    else:
        st.info("🧠 Por ahora solo puedo responder preguntas sobre las ventas del año 2025.")
