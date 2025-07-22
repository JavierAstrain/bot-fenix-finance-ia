import streamlit as st
import gspread
import json
from google.oauth2.service_account import Credentials

# Convertir el string JSON a dict
creds_json = st.secrets["GOOGLE_CREDENTIALS"]
creds_dict = json.loads(creds_json)

# Agregar scopes necesarios
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
client = gspread.authorize(creds)

# URL limpia
spreadsheet_url = "https://docs.google.com/spreadsheets/d/1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk"
sheet = client.open_by_url(spreadsheet_url).sheet1

# Mostrar algunas filas
data = sheet.get_all_values()
st.write(data[:5])
