import streamlit as st
import json
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="🤖 Fénix Bot Controller IA")
st.title("\U0001F916 Fénix Bot Controller IA")
st.markdown("Este bot es un analista financiero digital. Hazle una pregunta:")

# Cargar credenciales desde secrets.toml
creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
credentials = Credentials.from_service_account_info(creds_dict)
client = gspread.authorize(credentials)

# Abrir la hoja de Google Sheets
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk/edit#gid=0")
worksheet = sheet.sheet1

# Interfaz de entrada del usuario
pregunta = st.text_input("Tu pregunta:")

if pregunta:
    st.write("Procesando tu consulta...")

    # Guardar en la hoja
    worksheet.append_row([pregunta])

    # Aquí debería ir tu lógica de respuesta con IA (GPT, etc)
    respuesta = "Estoy procesando tu información y te responderé pronto."

    # Mostrar respuesta en la app
    st.success(respuesta)
