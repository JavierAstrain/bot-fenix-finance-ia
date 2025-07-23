import streamlit as st
import pandas as pd
import gspread
import json
import requests
from google.oauth2.service_account import Credentials

# --- CREDENCIALES GOOGLE DESDE SECRETS ---
try:
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    scope = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
except KeyError:
    st.error("❌ GOOGLE_CREDENTIALS no encontradas en st.secrets. Asegúrate de configurarlas correctamente.")
    st.stop()
except Exception as e:
    st.error("❌ Error al cargar las credenciales de Google.")
    st.exception(e)
    st.stop()


# --- CARGA DATOS DESDE GOOGLE SHEET ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk"

try:
    sheet = client.open_by_url(SHEET_URL).sheet1
    data = sheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df["Monto Facturado"] = pd.to_numeric(df["Monto Facturado"], errors="coerce")

    # --- UI ---
    st.title("🤖 Bot Fénix Finance IA")
    st.write("Haz preguntas en lenguaje natural sobre tu información financiera.")
    st.subheader("📊 Vista previa:")
    st.dataframe(df.head(10))

    st.subheader("💬 ¿Qué deseas saber?")
    pregunta = st.text_input("Ej: ¿Cuáles fueron las ventas del año 2025?")

    if pregunta:
        contexto = f"""Estos son datos financieros (primeras filas):

{df.head(20).to_string(index=False)}

Ahora responde esta pregunta de forma clara y concreta en español:

{pregunta}
"""
        # --- Configuración para la API de Google Gemini ---
        try:
            # Asegúrate de que GOOGLE_GEMINI_API_KEY esté configurada en .streamlit/secrets.toml
            google_gemini_api_key = st.secrets["GOOGLE_GEMINI_API_KEY"]
        except KeyError:
            st.error("❌ GOOGLE_GEMINI_API_KEY no encontrada en st.secrets. Por favor, configúrala en .streamlit/secrets.toml")
            st.stop() # Detiene la ejecución si la clave no está presente

        # URL de la API de Gemini (usando gemini-2.0-flash para la capa gratuita)
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={google_gemini_api_key}"

        # El formato del payload (cuerpo de la solicitud) para Gemini
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": contexto} # El contexto va aquí como parte del mensaje del usuario
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.3 # La temperatura se configura aquí
            }
        }

        headers = {
            "Content-Type": "application/json"
            # Para Gemini, la clave API va en la URL, no se necesita "Authorization: Bearer" en los headers
        }

        try:
            with st.spinner("Consultando IA de Google Gemini..."):
                response = requests.post(
                    api_url,
                    headers=headers,
                    json=payload
                )
                if response.status_code == 200:
                    # La estructura de la respuesta de Gemini es diferente a la de OpenRouter
                    response_data = response.json()
                    if response_data and "candidates" in response_data and len(response_data["candidates"]) > 0:
                        content = response_data["candidates"][0]["content"]["parts"][0]["text"]
                        st.success("🤖 Respuesta de Gemini:")
                        st.write(content)
                    else:
                        st.error("❌ No se recibió una respuesta válida de Gemini.")
                        st.text(response.text) # Muestra la respuesta completa para depuración
                else:
                    st.error(f"❌ Error al consultar Gemini API: {response.status_code}")
                    st.text(response.text) # Muestra el texto de la respuesta para depuración
        except Exception as e:
            st.error("❌ Falló la conexión con la API de Gemini.")
            st.exception(e)

except Exception as e:
    st.error("❌ No se pudo cargar la hoja de cálculo.")
    st.exception(e)

