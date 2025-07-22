import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
import matplotlib.pyplot as plt

# --- Configurar API ---
client_openai = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=st.secrets["OPENROUTER_API_KEY"]
)

# --- Conexión con Google Sheets ---
creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
creds = Credentials.from_service_account_info(creds_dict)
client_gs = gspread.authorize(creds)
spreadsheet_url = "https://docs.google.com/spreadsheets/d/1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk"
sheet = client_gs.open_by_url(spreadsheet_url).sheet1
data = sheet.get_all_values()
df = pd.DataFrame(data[1:], columns=data[0])

# --- Limpieza ---
df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
df["Monto Facturado"] = pd.to_numeric(df["Monto Facturado"], errors="coerce")

# --- Interfaz Streamlit ---
st.title("🤖 Bot Fénix Finance IA")
st.write("Controller financiero inteligente para tu negocio")

st.subheader("📊 Datos actuales:")
st.dataframe(df)

st.subheader("💬 Hazme una pregunta sobre los datos:")
pregunta = st.text_input("Escribe tu pregunta:")

if pregunta:
    contexto = f"""Estos son los datos financieros:
{df.head(10).to_string(index=False)}
"""
    prompt = f"{contexto}\n\nResponde esta pregunta del usuario de forma clara y profesional en español:\n{pregunta}"

    with st.spinner("Pensando..."):
        respuesta = client_openai.chat.completions.create(
            model="mistralai/mixtral-8x7b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        st.success("Respuesta:")
        st.write(respuesta.choices[0].message.content)

    # Extra: si en la pregunta hay "gráfico" o "evolución mensual", graficar
    if "gráfico" in pregunta.lower() or "evolución" in pregunta.lower():
        df_mes = df.groupby(df["Fecha"].dt.to_period("M"))["Monto Facturado"].sum().reset_index()
        df_mes["Fecha"] = df_mes["Fecha"].astype(str)
        plt.figure(figsize=(10,5))
        plt.plot(df_mes["Fecha"], df_mes["Monto Facturado"], marker="o")
        plt.title("Evolución mensual del Monto Facturado")
        plt.xticks(rotation=45)
        plt.grid(True)
        st.pyplot(plt)
