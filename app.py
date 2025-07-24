import streamlit as st
import pandas as pd
import gspread
import json
import requests
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime

# --- Configuración Constantes ---
USERNAME = "javier"
PASSWORD = "javier"
SHEET_URL = "https://docs.google.com/spreadsheets/d/1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk"
LOGO_PATH = "logo_high_resolution.jpg"

# --- Estado de Sesión ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# --- Funciones Auxiliares ---

def show_login_form():
    """Muestra el formulario de inicio de sesión."""
    st.title("🔒 Iniciar Sesión en Bot Fénix Finance IA")
    st.write("Por favor, introduce tus credenciales para acceder.")
    with st.form("login_form"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submit_button = st.form_submit_button("Iniciar Sesión")
        if submit_button:
            if username == USERNAME and password == PASSWORD:
                st.session_state.logged_in = True
                st.rerun()  # Vuelve a ejecutar el script para mostrar la app principal
            else:
                st.error("Usuario o contraseña incorrectos.")

@st.cache_data(ttl=600) # Cachea los datos por 10 minutos para mejorar rendimiento
def load_data(url):
    """Carga y procesa los datos desde Google Sheets."""
    try:
        creds_dict = st.secrets["GOOGLE_CREDENTIALS"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
        client = gspread.authorize(creds)
        sheet = client.open_by_url(url).sheet1
        data = sheet.get_all_values()
        
        if not data or len(data) < 2:
            st.warning("La hoja de cálculo está vacía o no tiene cabeceras.")
            return pd.DataFrame()

        df = pd.DataFrame(data[1:], columns=data[0])
        
        # Procesamiento y limpieza de datos
        if "Fecha" in df.columns:
            df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
        if "Monto Facturado" in df.columns:
            df["Monto Facturado"] = pd.to_numeric(df["Monto Facturado"], errors="coerce")
        
        df.dropna(subset=["Fecha", "Monto Facturado"], inplace=True)
        return df
    except Exception as e:
        st.error(f"❌ Error al cargar o procesar los datos: {e}")
        return pd.DataFrame()

def create_visualization(df, params):
    """Crea y muestra una visualización (gráfico o tabla) usando Plotly."""
    chart_type = params.get("chart_type")
    x_col = params.get("x_axis")
    y_col = params.get("y_axis")
    color_col = params.get("color_column") if params.get("color_column") else None

    # Validar que las columnas necesarias existan
    required_cols = [c for c in [x_col, y_col, color_col] if c]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        st.error(f"Error: El modelo solicitó columnas que no existen en los datos: {', '.join(missing_cols)}. Por favor, verifica tu pregunta o los nombres de las columnas en la hoja de cálculo.")
        return

    try:
        if chart_type == "table":
            # Para tablas, es útil agrupar y sumar
            grouping_cols = [col for col in [x_col, color_col] if col]
            if not grouping_cols:
                st.dataframe(df)
                return
            
            agg_df = df.groupby(grouping_cols)[y_col].sum().reset_index()
            st.dataframe(agg_df)

        elif chart_type in ["line", "bar", "scatter"]:
            # Agrupar datos para visualizaciones, especialmente si X es una fecha
            if pd.api.types.is_datetime64_any_dtype(df[x_col]):
                # Agrupar por mes para tener una vista más limpia
                plot_df = df.set_index(x_col).groupby([pd.Grouper(freq='ME'), color_col] if color_col else pd.Grouper(freq='ME'))[y_col].sum().reset_index()
            else:
                plot_df = df.groupby([x_col] + ([color_col] if color_col else []))[y_col].sum().reset_index()

            title = f"{y_col} por {x_col}" + (f" separado por {color_col}" if color_col else "")
            
            if chart_type == "line":
                fig = px.line(plot_df, x=x_col, y=y_col, color=color_col, title=title, markers=True)
            elif chart_type == "bar":
                fig = px.bar(plot_df, x=x_col, y=y_col, color=color_col, title=title)
            elif chart_type == "scatter":
                 fig = px.scatter(plot_df, x=x_col, y=y_col, color=color_col, title=title)
            st.plotly_chart(fig, use_container_width=True)

        elif chart_type == "pie":
            fig = px.pie(df, names=x_col, values=y_col, color=color_col, title=f"Distribución de {y_col} por {x_col}")
            st.plotly_chart(fig, use_container_width=True)
            
    except Exception as e:
        st.error(f"Ha ocurrido un error al generar la visualización: {e}")

def main_app():
    """Función principal que se ejecuta después del login."""
    try:
        st.image(LOGO_PATH, width=200)
    except FileNotFoundError:
        st.warning(f"Logo no encontrado en la ruta: '{LOGO_PATH}'.")

    st.title("🤖 Bot Fénix Finance IA")
    df = load_data(SHEET_URL)

    if df.empty:
        st.info("Esperando datos para analizar... Asegúrate de que la hoja de cálculo esté accesible y con datos.")
        st.stop()
        
    st.write("Haz preguntas en lenguaje natural sobre tu información financiera.")
    st.subheader("📊 Vista previa de los datos:")
    st.dataframe(df.head())
    
    with st.expander("💡 ¿Qué puedes preguntar?"):
        st.write("""
        **Consultas de datos y análisis:**
        - *¿Cuál fue el monto total facturado en 2024?*
        - *Dame un análisis de las ventas del último trimestre.*
        - *¿Qué cliente generó más ingresos?*

        **Peticiones de gráficos y tablas:**
        - *Muéstrame una tabla con las ventas por TipoCliente.*
        - *Crea un gráfico de líneas con la evolución del Monto Facturado.*
        - *Haz un gráfico de barras del Monto Facturado por mes, separado por TipoCliente.*
        """)

    # --- Lógica de Interacción con Gemini ---
    if prompt := st.text_input("Escribe tu pregunta aquí:", key="prompt_input"):
        try:
            api_key = st.secrets["GOOGLE_GEMINI_API_KEY"]
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro-latest:generateContent?key={api_key}"
            
            # Contexto simplificado para la IA
            data_sample = df.head(5).to_csv(index=False)
            column_names = ", ".join(df.columns)
            
            # Prompt unificado y más inteligente
            system_prompt = f"""
            Eres un asistente de análisis de datos experto llamado Fénix. Tu objetivo es ayudar a un usuario a entender sus datos financieros.
            Analiza la pregunta del usuario y decide qué herramienta usar: `answer_question` para respuestas textuales o `generate_chart_or_table` para visualizaciones.

            **Contexto de los Datos:**
            - Los datos son un registro de transacciones financieras.
            - Columnas disponibles: {column_names}
            - Aquí tienes una muestra de los datos en formato CSV para que entiendas la estructura:
            ```csv
            {data_sample}
            ```

            **Herramientas Disponibles:**
            1. `answer_question`: Úsala para preguntas generales, análisis, resúmenes, cálculos de totales, promedios, máximos/mínimos, o cualquier consulta que pueda responderse con texto.
            2. `generate_chart_or_table`: Úsala cuando el usuario pida explícitamente un "gráfico", "tabla", "evolución", "distribución", "comparación visual", "lista detallada" o "muéstrame".

            **Responde SIEMPRE en formato JSON.**

            **Ejemplos:**
            - Usuario: "¿Cuál fue el monto total facturado?" -> Responde con `answer_question`.
            - Usuario: "Analiza las ventas de 2024." -> Responde con `answer_question`.
            - Usuario: "Gráfico de la evolución de ventas" -> Responde con `generate_chart_or_table`.
            - Usuario: "Muéstrame una tabla de ventas por cliente" -> Responde con `generate_chart_or_table`.

            **Pregunta del Usuario:** "{prompt}"
            """

            payload = {
                "contents": [{"parts": [{"text": system_prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": {
                        "type": "OBJECT",
                        "properties": {
                            "tool_choice": {
                                "type": "STRING",
                                "enum": ["answer_question", "generate_chart_or_table"]
                            },
                            "tool_parameters": {
                                "type": "OBJECT",
                                "properties": {
                                    "text_answer": {"type": "STRING"},
                                    "chart_type": {"type": "STRING", "enum": ["line", "bar", "pie", "scatter", "table"]},
                                    "x_axis": {"type": "STRING"},
                                    "y_axis": {"type": "STRING"},
                                    "color_column": {"type": "STRING"}
                                }
                            }
                        }
                    }
                }
            }

            with st.spinner("🧠 Fénix está pensando..."):
                response = requests.post(api_url, headers={"Content-Type": "application/json"}, json=payload, timeout=60)
                response.raise_for_status() # Lanza un error si la respuesta no es 2xx
                
                response_data = response.json()
                content_text = response_data["candidates"][0]["content"]["parts"][0]["text"]
                result = json.loads(content_text)
                
                tool = result.get("tool_choice")
                params = result.get("tool_parameters", {})

                if tool == "generate_chart_or_table":
                    st.success("Hecho. Aquí tienes la visualización que pediste:")
                    create_visualization(df, params)
                elif tool == "answer_question":
                    st.success("Hecho. Aquí tienes la respuesta a tu pregunta:")
                    st.markdown(params.get("text_answer", "No se pudo generar una respuesta."))
                else:
                    st.warning("No pude determinar cómo responder a tu solicitud. Intenta reformular la pregunta.")

        except requests.exceptions.HTTPError as http_err:
            st.error(f"❌ Error en la API de Gemini: {http_err}. Respuesta: {response.text}")
        except Exception as e:
            st.error(f"❌ Ocurrió un error inesperado: {e}")
            
# --- Flujo Principal de la Aplicación ---
if not st.session_state.logged_in:
    show_login_form()
else:
    main_app()
