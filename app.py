import streamlit as st
import openai
import gspread
import json
import os
from google.oauth2.service_account import Credentials

# ---------------------------
# Configuración de página
# ---------------------------
st.set_page_config(page_title="Fénix Bot Controller IA")

st.title("🤖 Fénix Bot Controller IA")
st.write("Este bot es un analista financiero digital. Hazle una pregunta:")

# ---------------------------
# Cargar credenciales desde Secrets
# ---------------------------
creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
credentials = Credentials.from_service_account_info(creds_dict)
client = gspread.authorize(credentials)

# ---------------------------
# Abrir hoja de Google Sheets
# ---------------------------
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1q1qU7QIXxBES6QOJyi25r5_Udf-c9nEGUKlb_Ya_yZQ/edit#gid=0")
worksheet = sheet.worksheet("Hoja 1")
data = worksheet.get_all_records()

# ---------------------------
# Preparar contexto para GPT
# ---------------------------
contexto = "Eres un analista financiero que responde usando solo esta información:\n"
for row in data:
    contexto += json.dumps(row, ensure_ascii=False) + "\n"

# ---------------------------
# Entrada del usuario
# ---------------------------
user_input = st.text_input("Tu pregunta:")

if user_input:
    with st.spinner("Analizando información financiera..."):
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": contexto},
                {"role": "user", "content": user_input}
            ],
            temperature=0.3,
            max_tokens=500
        )
        respuesta = response.choices[0].message["content"]
        st.success(respuesta)
