import streamlit as st
import openai
import gspread
import pandas as pd
import os
import json
import gspread
from google.oauth2.service_account import Credentials

# Autenticación segura desde Secrets
creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
credentials = Credentials.from_service_account_info(creds_dict)
gc = gspread.authorize(credentials)

st.set_page_config(page_title="Fénix Bot Controller IA", layout="centered")

st.title("🤖 Fénix Bot Controller IA")
st.markdown("Este bot es un analista financiero digital. Hazle una pregunta:")

user_question = st.text_input("Tu pregunta:")

if user_question:
    try:
        # Autenticación con Google Sheets
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        credentials = ServiceAccountCredentials.from_json_keyfile_name("credenciales.json", scope)
        client = gspread.authorize(credentials)

        # Abrir hoja de cálculo y leer datos
        sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1v0o5qHVFKhfJx9xGxVoqSbP-i-vKrhx4cI7c7tU3cnA/edit#gid=0")
        worksheet = sheet.sheet1
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)

        # Preparar prompt
        system_prompt = {
            "role": "system",
            "content": f"Eres un analista financiero que responde usando solo esta información:\n{df.to_string(index=False)}"
        }

        messages = [
            system_prompt,
            {"role": "user", "content": user_question}
        ]

        # Llamada a la API de OpenAI
        openai.api_key = st.secrets["OPENAI_API_KEY"]
        response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
        st.markdown(f"**Respuesta:** {response.choices[0].message.content.strip()}")
    except Exception as e:
        st.error(f"Error: {e}")
