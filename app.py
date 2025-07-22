import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# Cargar credenciales desde secrets
creds_dict = st.secrets["GOOGLE_CREDENTIALS"]
creds = Credentials.from_service_account_info(creds_dict)
client = gspread.authorize(creds)

# URL limpia
spreadsheet_url = "https://docs.google.com/spreadsheets/d/1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk"
sheet = client.open_by_url(spreadsheet_url).sheet1

# Mostrar algunas filas
data = sheet.get_all_values()
st.write(data[:5])
