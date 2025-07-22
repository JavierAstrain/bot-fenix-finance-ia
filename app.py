import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Fénix Bot Controller IA", page_icon="🧠")

st.title("🧠 Fénix Bot Controller IA")
st.markdown("Este bot es un analista financiero digital. Hazle una pregunta:")

# ========================
# Cargar credenciales desde st.secrets (ya es dict)
# ========================
creds_dict = st.secrets["GOOGLE_CREDENTIALS"]

# Crear objeto Credentials
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)

# Autenticación con gspread
client = gspread.authorize(credentials)

# ========================
# Conectar con la hoja de cálculo
# ========================
spreadsheet_url = "https://docs.google.com/spreadsheets/d/1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk/edit#gid=0"
sheet = client.open_by_url(spreadsheet_url)
worksheet = sheet.sheet1

# ========================
# Interfaz de usuario
# ========================
user_input = st.text_input("Escribe tu consulta:")

if user_input:
    st.markdown("🤖 *Procesando tu consulta...*")

    # Simulación de respuesta con IA (aquí puedes integrar GPT si deseas)
    respuesta = f"Tu consulta fue: **{user_input}**\n\n(Esto es una respuesta simulada.)"

    # Mostrar respuesta
    st.success(respuesta)

    # Registrar en Sheets
    worksheet.append_row([user_input, respuesta])
