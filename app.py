import streamlit as st
import gspread
import json
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Fénix Finance Bot", layout="centered")

st.title("🤖 Bot Fénix Finance IA")
st.write("Conecta datos financieros desde Google Sheets para control inteligente.")

# URL de tu hoja de cálculo
spreadsheet_url = "https://docs.google.com/spreadsheets/d/1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk/edit#gid=0"

# Cargar credenciales desde secrets TOML (como string JSON)
credentials_json = st.secrets["GOOGLE_CREDENTIALS"]
creds_dict = json.loads(credentials_json)

# Crear objeto de credenciales
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)

# Autenticarse y abrir hoja
client = gspread.authorize(credentials)
sheet = client.open_by_url(spreadsheet_url).sheet1

# Mostrar contenido actual de la hoja
data = sheet.get_all_records()
if data:
    st.subheader("📊 Datos actuales:")
    st.dataframe(data)
else:
    st.info("No hay datos aún en la hoja.")

# Formulario de ingreso
st.subheader("➕ Ingresar nuevo dato")

with st.form("data_form"):
    fecha = st.date_input("Fecha")
    descripcion = st.text_input("Descripción")
    monto = st.number_input("Monto", step=1000)
    tipo = st.selectbox("Tipo", ["Ingreso", "Gasto"])
    submitted = st.form_submit_button("Agregar")

    if submitted:
        sheet.append_row([str(fecha), descripcion, monto, tipo])
        st.success("✅ Dato agregado correctamente.")
        st.rerun()
