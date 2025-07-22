import streamlit as st
import gspread
import json
from google.oauth2.service_account import Credentials

st.title("🔧 Bot financiero Fénix Automotriz")

# URL del Google Sheet
spreadsheet_url = "https://docs.google.com/spreadsheets/d/1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk/edit#gid=0"

# Leer credenciales desde secrets
creds_json = st.secrets["GOOGLE_CREDENTIALS"]
creds_dict = json.loads(creds_json)

# Crear credenciales
credentials = Credentials.from_service_account_info(creds_dict)

# Conectar con Google Sheets
client = gspread.authorize(credentials)
sheet = client.open_by_url(spreadsheet_url)
worksheet = sheet.get_worksheet(0)  # Primera hoja

# Mostrar algunas celdas (ejemplo)
st.write("Primeras filas:")
st.dataframe(worksheet.get_all_records())
