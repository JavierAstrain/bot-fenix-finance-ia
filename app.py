import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json

# Cargar credenciales desde secrets
creds_dict = st.secrets["GOOGLE_CREDENTIALS"]
credentials = Credentials.from_service_account_info(creds_dict)

# Autenticarse con gspread
client = gspread.authorize(credentials)

# Abrir la hoja
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk/edit#gid=0")
worksheet = sheet.sheet1

# Mostrar algo simple
st.title("✅ Conexión exitosa a Google Sheets")
data = worksheet.get_all_records()
st.write(data)
