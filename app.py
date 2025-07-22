import streamlit as st
import pandas as pd
import json
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI

st.set_page_config(page_title="Bot Financiero Fénix", layout="centered")
st.title("🤖 Bot Financiero de Fénix Automotriz")

# --- CREDENCIALES GOOGLE ---
creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
credentials = Credentials.from_service_account_info(creds_dict)
client = gspread.authorize(credentials)

# --- URL DE GOOGLE SHEET ---
spreadsheet_url = "https://docs.google.com/spreadsheets/d/1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk/edit#gid=0"
sheet = client.open_by_url(spreadsheet_url).sheet1

# --- CARGA DE DATOS ---
data = sheet.get_all_records()
df = pd.DataFrame(data)

# --- INSTRUCCIONES ---
st.markdown("""
Este bot responderá tus preguntas basándose en la información financiera contenida en la hoja de cálculo.
Por ejemplo:
- ¿Cuánto se vendió en enero?
- ¿Cuál fue la utilidad total del mes?
""")

# --- INPUT DE USUARIO ---
pregunta = st.text_input("Haz tu pregunta sobre los datos:")

if pregunta:
    with st.spinner("Consultando a la IA..."):
        client_openai = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

        # Convierte el dataframe a texto para pasar como contexto
        table_text = df.to_markdown(index=False)

        prompt = f"""
Eres un asistente financiero. Responde la siguiente pregunta basándote exclusivamente en la siguiente tabla:

{table_text}

Pregunta: {pregunta}
"""

        response = client_openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un asistente financiero experto."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )

        respuesta = response.choices[0].message.content
        st.success("Respuesta de la IA:")
        st.write(respuesta)
