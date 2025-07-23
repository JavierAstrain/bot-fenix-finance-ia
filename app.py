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
        # --- Contexto mejorado para análisis, predicciones y recomendaciones ---
        contexto = f"""Eres un asistente de IA especializado en análisis financiero. Tu misión es ayudar al usuario a interpretar sus datos, identificar tendencias, predecir posibles escenarios (con cautela) y ofrecer recomendaciones estratégicas.

        Aquí están las **primeras 20 filas** de los datos financieros disponibles para tu análisis:

        {df.head(20).to_string(index=False)}

        Basándote **exclusivamente** en la información proporcionada y en tu rol de analista financiero, por favor, responde a la siguiente pregunta del usuario.

        Al formular tu respuesta, considera lo siguiente:
        1.  **Análisis:** Busca patrones, anomalías, crecimientos o decrecimientos significativos.
        2.  **Predicción (si aplica):** Si la pregunta sugiere una proyección, basa tu estimación en las tendencias históricas visibles en los datos. **IMPORTANTE: Siempre aclara que cualquier predicción es una estimación basada en datos pasados y no una garantía ni un consejo financiero.**
        3.  **Recomendaciones:** Ofrece consejos prácticos y accionables que el usuario pueda considerar para mejorar su situación financiera, siempre fundamentados en el análisis de los datos.
        4.  **Tono:** Mantén un tono profesional, claro, conciso y empático.
        5.  **Idioma:** Responde siempre en español.

        ---
        Pregunta del usuario:
        {pregunta}
        """

        # --- Configuración para la API de Google Gemini ---
        try:
            google_gemini_api_key = st.secrets["GOOGLE_GEMINI_API_KEY"]
        except KeyError:
            st.error("❌ GOOGLE_GEMINI_API_KEY no encontrada en st.secrets. Por favor, configúrala en .streamlit/secrets.toml")
            st.stop()

        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={google_gemini_api_key}"

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": contexto}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.3
            }
        }

        headers = {
            "Content-Type": "application/json"
        }

        try:
            with st.spinner("Consultando IA de Google Gemini..."):
                response = requests.post(
                    api_url,
                    headers=headers,
                    json=payload
                )
                if response.status_code == 200:
                    response_data = response.json()
                    if response_data and "candidates" in response_data and len(response_data["candidates"]) > 0:
                        content = response_data["candidates"][0]["content"]["parts"][0]["text"]
                        st.success("🤖 Respuesta de Gemini:")
                        st.write(content)
                    else:
                        st.error("❌ No se recibió una respuesta válida de Gemini.")
                        st.text(response.text)
                else:
                    st.error(f"❌ Error al consultar Gemini API: {response.status_code}")
                    st.text(response.text)
        except Exception as e:
            st.error("❌ Falló la conexión con la API de Gemini.")
            st.exception(e)

except Exception as e:
    st.error("❌ No se pudo cargar la hoja de cálculo.")
    st.exception(e)

