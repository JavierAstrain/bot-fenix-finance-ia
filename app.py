import streamlit as st
import pandas as pd
import gspread
import json
import requests
from google.oauth2.service_account import Credentials
import plotly.express as px # Importamos Plotly para los gráficos

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

    # Eliminar filas con valores NaN en columnas críticas para el análisis o gráficos
    df.dropna(subset=["Fecha", "Monto Facturado"], inplace=True)

    # --- UI ---
    st.title("🤖 Bot Fénix Finance IA")
    st.write("Haz preguntas en lenguaje natural sobre tu información financiera.")
    st.subheader("📊 Vista previa:")
    st.dataframe(df.head(10))

    st.subheader("💬 ¿Qué deseas saber?")
    pregunta = st.text_input("Ej: ¿Cuáles fueron las ventas del año 2025? o Hazme un gráfico de la evolución de ventas del 2025.")

    if pregunta:
        # --- Configuración para la API de Google Gemini ---
        try:
            google_gemini_api_key = st.secrets["GOOGLE_GEMINI_API_KEY"]
        except KeyError:
            st.error("❌ GOOGLE_GEMINI_API_KEY no encontrada en st.secrets. Por favor, configúrala en .streamlit/secrets.toml")
            st.stop()

        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={google_gemini_api_key}"

        # --- PRIMERA LLAMADA A GEMINI: DETECTAR INTENCIÓN DE GRÁFICO Y EXTRAER PARÁMETROS ---
        # Le pedimos a Gemini que nos devuelva un JSON estructurado para el gráfico
        chart_detection_payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": f"""Analiza la siguiente pregunta del usuario y determina si solicita un gráfico.
                            Si es así, extrae el tipo de gráfico, las columnas para los ejes X e Y, y cualquier filtro de fecha o valor.
                            Si no es una solicitud de gráfico, marca 'is_chart_request' como false.

                            Datos disponibles y sus columnas:
                            - 'Fecha' (tipo fecha)
                            - 'Monto Facturado' (tipo numérico)

                            Ejemplos de cómo mapear la intención:
                            - "evolución de ventas del año 2025": chart_type='line', x_axis='Fecha', y_axis='Monto Facturado', filter_column='Fecha', filter_value='2025'
                            - "ventas por mes": chart_type='bar', x_axis='Fecha', y_axis='Monto Facturado', filter_column='', filter_value=''
                            - "gráfico de barras de montos facturados": chart_type='bar', x_axis='Fecha', y_axis='Monto Facturado', filter_column='', filter_value=''

                            Pregunta del usuario: "{pregunta}"
                            """
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "OBJECT",
                    "properties": {
                        "is_chart_request": {
                            "type": "BOOLEAN",
                            "description": "True si el usuario pide un gráfico, false en caso contrario."
                        },
                        "chart_type": {
                            "type": "STRING",
                            "enum": ["line", "bar", "pie", "scatter", "none"],
                            "description": "Tipo de gráfico (line, bar, pie, scatter). 'none' si no es un gráfico o tipo no claro."
                        },
                        "x_axis": {
                            "type": "STRING",
                            "description": "Nombre de la columna para el eje X (ej: 'Fecha'). Vacío si no es gráfico."
                        },
                        "y_axis": {
                            "type": "STRING",
                            "description": "Nombre de la columna para el eje Y (ej: 'Monto Facturado'). Vacío si no es gráfico."
                        },
                        "filter_column": {
                            "type": "STRING",
                            "description": "Columna para filtrar (ej: 'Fecha'). Vacío si no hay filtro."
                        },
                        "filter_value": {
                            "type": "STRING",
                            "description": "Valor para filtrar (ej: '2025', 'Enero'). Vacío si no hay filtro."
                        },
                        "summary_response": {
                            "type": "STRING",
                            "description": "Respuesta conversacional si se genera un gráfico. Vacío si no es gráfico."
                        }
                    },
                    "required": ["is_chart_request", "chart_type", "x_axis", "y_axis", "filter_column", "filter_value", "summary_response"]
                }
            }
        }

        try:
            with st.spinner("Analizando su solicitud..."):
                chart_response = requests.post(api_url, headers={"Content-Type": "application/json"}, json=chart_detection_payload)
                chart_data = json.loads(chart_response.json()["candidates"][0]["content"]["parts"][0]["text"])

            if chart_data.get("is_chart_request"):
                st.success(chart_data.get("summary_response", "Aquí tienes el gráfico solicitado:"))

                filtered_df = df.copy()
                # Aplicar filtro si existe
                if chart_data["filter_column"] and chart_data["filter_value"]:
                    if chart_data["filter_column"] == "Fecha":
                        try:
                            # Intentar filtrar por año
                            year_to_filter = int(chart_data["filter_value"])
                            filtered_df = filtered_df[filtered_df["Fecha"].dt.year == year_to_filter]
                        except ValueError:
                            # Si no es un año, intentar filtrar por mes (ej. "Enero")
                            month_name = chart_data["filter_value"].lower()
                            month_map = {
                                'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
                                'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
                                'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
                            }
                            if month_name in month_map:
                                filtered_df = filtered_df[filtered_df["Fecha"].dt.month == month_map[month_name]]
                            else:
                                st.warning(f"No se pudo aplicar el filtro de fecha '{chart_data['filter_value']}'. Mostrando todos los datos relevantes.")
                    else:
                        # Para otros tipos de columnas de filtro
                        filtered_df = filtered_df[filtered_df[chart_data["filter_column"]].astype(str).str.contains(chart_data["filter_value"], case=False, na=False)]

                # Asegurarse de que haya datos después de filtrar
                if filtered_df.empty:
                    st.warning("No hay datos para generar el gráfico con los filtros especificados.")
                else:
                    # Generar el gráfico con Plotly
                    fig = None
                    if chart_data["chart_type"] == "line":
                        fig = px.line(filtered_df, x=chart_data["x_axis"], y=chart_data["y_axis"],
                                      title=f"Evolución de {chart_data['y_axis']} por {chart_data['x_axis']}",
                                      labels={chart_data["x_axis"]: chart_data["x_axis"], chart_data["y_axis"]: chart_data["y_axis"]})
                    elif chart_data["chart_type"] == "bar":
                        fig = px.bar(filtered_df, x=chart_data["x_axis"], y=chart_data["y_axis"],
                                     title=f"Distribución de {chart_data['y_axis']} por {chart_data['x_axis']}",
                                     labels={chart_data["x_axis"]: chart_data["x_axis"], chart_data["y_axis"]: chart_data["y_axis"]})
                    elif chart_data["chart_type"] == "pie":
                        # Para gráficos de pastel, necesitamos agrupar los datos
                        # Asumimos que x_axis es la categoría y y_axis el valor a sumar
                        grouped_df = filtered_df.groupby(chart_data["x_axis"])[chart_data["y_axis"]].sum().reset_index()
                        fig = px.pie(grouped_df, names=chart_data["x_axis"], values=chart_data["y_axis"],
                                     title=f"Proporción de {chart_data['y_axis']} por {chart_data['x_axis']}")
                    elif chart_data["chart_type"] == "scatter":
                        fig = px.scatter(filtered_df, x=chart_data["x_axis"], y=chart_data["y_axis"],
                                         title=f"Relación entre {chart_data['x_axis']} y {chart_data['y_axis']}",
                                         labels={chart_data["x_axis"]: chart_data["x_axis"], chart_data["y_axis"]: chart_data["y_axis"]})

                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("No se pudo generar el tipo de gráfico solicitado o los datos no son adecuados.")

            else: # Si no es una solicitud de gráfico, procede con el análisis de texto
                # --- SEGUNDA LLAMADA A GEMINI: ANÁLISIS Y RECOMENDACIONES (como antes) ---
                contexto_analisis = f"""Eres un asistente de IA especializado en análisis financiero. Tu misión es ayudar al usuario a interpretar sus datos, identificar tendencias, predecir posibles escenarios (con cautela) y ofrecer recomendaciones estratégicas.

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

                text_generation_payload = {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {"text": contexto_analisis}
                            ]
                        }
                    ],
                    "generationConfig": {
                        "temperature": 0.3
                    }
                }

                with st.spinner("Consultando IA de Google Gemini..."):
                    response = requests.post(api_url, headers={"Content-Type": "application/json"}, json=text_generation_payload)
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

        except json.JSONDecodeError:
            st.error("❌ Error al procesar la respuesta JSON del modelo. Intente de nuevo o reformule la pregunta.")
            st.text(chart_response.text if 'chart_response' in locals() else "No se pudo obtener una respuesta.")
        except Exception as e:
            st.error("❌ Falló la conexión con la API de Gemini o hubo un error inesperado.")
            st.exception(e)

except Exception as e:
    st.error("❌ No se pudo cargar la hoja de cálculo.")
    st.exception(e)

