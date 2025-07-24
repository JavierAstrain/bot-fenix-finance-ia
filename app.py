import streamlit as st
import pandas as pd
import gspread
import json
import requests
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime

# --- Configuración de Login ---
USERNAME = "adm"
PASSWORD = "adm"

# Inicializar el estado de la sesión para el login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# Función para el formulario de login
def show_login_form():
    st.title("🔒 Iniciar Sesión en Bot Fénix Finance IA")
    st.write("Por favor, introduce tus credenciales para acceder.")

    with st.form("login_form"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submit_button = st.form_submit_button("Iniciar Sesión")

        if submit_button:
            if username == USERNAME and password == PASSWORD:
                st.session_state.logged_in = True
                st.success("¡Sesión iniciada correctamente!")
            else:
                st.error("Usuario o contraseña incorrectos.")

# Mostrar el formulario de login si el usuario no ha iniciado sesión
if not st.session_state.logged_in: # Corregido de 'loggedin' a 'logged_in'
    show_login_form()
else:
    # --- El resto de tu código de la aplicación Streamlit va aquí ---

    # --- AGREGAR LOGO DE LA EMPRESA ---
    # Asegúrate de que 'logo_high_resolution.jpg' esté en la misma carpeta que app.py
    try:
        st.image("logo_high_resolution.jpg", width=200) # Ajusta el ancho según necesites
    except FileNotFoundError:
        st.warning("No se encontró el archivo 'logo_high_resolution.jpg'. Asegúrate de que esté en la misma carpeta.")
    
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
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk/edit?gid=0#gid=0"

    try:
        sheet = client.open_by_url(SHEET_URL).sheet1
        data = sheet.get_all_values()
        df = pd.DataFrame(data[1:], columns=data[0])
        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
        df["Monto Facturado"] = pd.to_numeric(df["Monto Facturado"], errors="coerce")

        # Eliminar filas con valores NaN en columnas críticas para el análisis o gráficos
        df.dropna(subset=["Fecha", "Monto Facturado"], inplace=True)

        # --- Generar información dinámica de columnas para el prompt de Gemini ---
        # Esta información se usará para el prompt de Gemini para que sepa qué columnas existen
        available_columns_info = []
        for col in df.columns:
            col_type = df[col].dtype
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                available_columns_info.append(f"- '{col}' (tipo fecha, formato YYYY-MM-DD)")
            elif pd.api.types.is_numeric_dtype(df[col]):
                available_columns_info.append(f"- '{col}' (tipo numérico)")
            else:
                # Para columnas de texto, intentar obtener los valores únicos más comunes
                unique_vals = df[col].dropna().unique()
                if len(unique_vals) < 10: # Si hay pocos valores únicos, listarlos todos
                    available_columns_info.append(f"- '{col}' (tipo texto, valores: {', '.join(map(str, unique_vals))})")
                else: # Si hay muchos, solo mencionar el tipo
                    available_columns_info.append(f"- '{col}' (tipo texto)")
        available_columns_str = "\n".join(available_columns_info)

        # --- Generar un resumen más completo del DataFrame para Gemini ---
        # Este resumen detallado le da a Gemini una visión completa de los datos sin enviar todo el DF
        df_summary_parts = []
        df_summary_parts.append("Resumen de la estructura del DataFrame:")
        df_summary_parts.append(f"Número total de filas: {len(df)}")
        df_summary_parts.append(f"Número total de columnas: {len(df.columns)}")
        
        df_summary_parts.append("\nInformación detallada de Columnas:")
        for col in df.columns:
            dtype = df[col].dtype
            non_null_count = df[col].count()
            total_count = len(df)
            null_percentage = (1 - non_null_count / total_count) * 100
            col_info = f"- Columna '{col}': Tipo '{dtype}', {non_null_count}/{total_count} valores no nulos ({null_percentage:.2f}% nulos)."
            
            if pd.api.types.is_numeric_dtype(df[col]):
                col_info += f" Estadísticas: Min={df[col].min():.2f}, Max={df[col].max():.2f}, Media={df[col].mean():.2f}, Suma={df[col].sum():.2f}"
            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                col_info += f" Rango de fechas: [{df[col].min().strftime('%Y-%m-%d')} a {df[col].max().strftime('%Y-%m-%d')}]"
            elif pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
                # Para columnas de texto, incluir los 10 valores más frecuentes y su conteo
                top_values_counts = df[col].value_counts().nlargest(10)
                if not top_values_counts.empty:
                    top_values_str = [f"'{val}' ({count})" for val, count in top_values_counts.items()]
                    col_info += f" Valores más frecuentes: {', '.join(top_values_str)}"
            df_summary_parts.append(col_info)
        
        df_summary_str = "\n".join(df_summary_parts)


        # --- UI ---
        st.title("🤖 Bot Fénix Finance IA")
        st.write("Haz preguntas en lenguaje natural sobre tu información financiera.")
        st.subheader("📊 Vista previa de los datos:")
        st.dataframe(df.head(10))

        # --- Sección de "Qué puedes preguntar" ---
        with st.expander("💡 ¿Qué puedes preguntar y cuáles son los alcances de este bot?"):
            st.write("""
            Este bot de Fénix Finance IA está diseñado para ayudarte a analizar tus datos financieros. Puedes:

            * **Consultar Datos Específicos y Generar Tablas:**
                * Ej: "¿Cuál fue el Monto Facturado total en el mes de marzo de 2025?"
                * Ej: "**Muéstrame una tabla** con los Montos Facturados por cada TipoCliente."
                * Ej: "**Lista** las 5 transacciones con mayor Monto Facturado."
                * Ej: "Dime el total de ventas para el TipoCliente 'Particular' en 2024."

            * **Generar Gráficos Interactivos:**
                * **Evolución:** "Hazme un gráfico de línea con la evolución de Monto Facturado en 2023."
                * **Comparación:** "Muestra un gráfico de barras del Monto Facturado por mes."
                * **Segmentación:** "Crea un gráfico de evolución de ventas de 2025 separado por TipoCliente."
                * **Rangos de Fecha:** "Gráfico de Monto Facturado entre 2024-01-15 y 2024-04-30."
                * **Tipos de Gráfico:** Línea, barras, pastel, dispersión.

            * **Realizar Análisis y Obtener Perspectivas:**
                * Ej: "¿Qué tendencias observas en mis Montos Facturados?"
                * Ej: "¿Hubo alguna anomalía en las ventas del último trimestre?"
                * Ej: "Dame un análisis de los datos de 2024."
                * Ej: "¿Cuál es el cliente que genera mayor cantidad de ventas?"

            * **Hacer Estimaciones y Proyecciones (con cautela):**
                * Ej: "¿Podrías proyectar el Monto Facturado para el próximo mes basándote en los datos históricos?"
                * **Alcance:** Las proyecciones se basan **únicamente** en los datos históricos proporcionados y son estimaciones. **No son consejos financieros garantizados.**

            * **Recibir Recomendaciones Estratégicas:**
                * Ej: "¿Qué recomendaciones me darías para mejorar mi Monto Facturado?"
                * **Alcance:** Las recomendaciones se derivan del análisis de tus datos y buscan ofrecer ideas accionables. **Siempre consulta con un profesional financiero antes de tomar decisiones importantes.**

            **Importante:**
            * El bot solo puede analizar la información presente en tu hoja de cálculo.
            * Asegúrate de que los nombres de las columnas que mencionas en tus preguntas (ej. 'Fecha', 'Monto Facturado', 'TipoCliente') coincidan **exactamente** con los de tu hoja.
            * Para análisis avanzados o gráficos segmentados, es necesario que las columnas relevantes existan en tus datos.
            """)

        # --- SECCIÓN: Verificación de API Key de Gemini ---
        with st.expander("🔑 Verificar API Key de Gemini"):
            st.write("Usa esta sección para probar si tu API Key de Google Gemini está configurada y funcionando correctamente.")
            test_api_key = st.text_input("Ingresa tu API Key de Gemini aquí (opcional, usa st.secrets si está vacío):", type="password")
            test_button = st.button("Probar API Key")

            if test_button:
                current_api_key = test_api_key if test_api_key else st.secrets.get("GOOGLE_GEMINI_API_KEY", "")
                
                if not current_api_key:
                    st.warning("No se ha proporcionado una API Key para la prueba ni se encontró en `st.secrets`.")
                else:
                    test_api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={current_api_key}"
                    test_payload = {
                        "contents": [
                            {
                                "role": "user",
                                "parts": [{"text": "Hello"}]
                            }
                        ]
                    }
                    try:
                        with st.spinner("Realizando prueba de API Key..."):
                            test_response = requests.post(test_api_url, headers={"Content-Type": "application/json"}, json=test_payload, timeout=10) # Añadir timeout
                        
                        st.subheader("Resultado de la Prueba:")
                        st.write(f"Código de estado HTTP: {test_response.status_code}")
                        st.json(test_response.json()) # Mostrar el JSON completo de la respuesta

                        if test_response.status_code == 200:
                            st.success("✅ ¡La API Key parece estar funcionando correctamente!")
                            if "candidates" in test_response.json() and len(test_response.json()["candidates"]) > 0:
                                st.write("Respuesta del modelo (extracto):", test_response.json()["candidates"][0]["content"]["parts"][0]["text"])
                            else:
                                st.warning("La API Key funciona, pero la respuesta del modelo no contiene el formato esperado.")
                        else:
                            st.error(f"❌ La API Key no está funcionando. Código de estado: {test_response.status_code}")
                            st.write("Posibles razones: clave incorrecta, límites de uso alcanzados, problemas de red, o la clave no tiene los permisos adecuados.")
                            st.write("Mensaje de error de la API:", test_response.text)

                    except requests.exceptions.Timeout:
                        st.error("❌ La solicitud a la API de Gemini ha excedido el tiempo de espera (timeout). Esto puede ser un problema de red o que el servidor de Gemini esté tardando en responder.")
                    except requests.exceptions.ConnectionError:
                        st.error("❌ Error de conexión a la API de Gemini. Verifica tu conexión a internet o si la URL de la API es correcta.")
                    except json.JSONDecodeError:
                        st.error("❌ La respuesta de la API no es un JSON válido. Esto podría indicar un problema en la API de Gemini o una respuesta inesperada.")
                    except Exception as e:
                        st.error(f"❌ Ocurrió un error inesperado durante la prueba de la API Key: {e}")

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

            # --- PRIMERA LLAMADA A GEMINI: DETECTAR INTENCIÓN Y EXTRAER PARÁMETROS ---
            chart_detection_payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": f"""Eres un asesor financiero impecable y tu objetivo es proporcionar análisis precisos, gráficos claros y respuestas directas y útiles.

                                Analiza la siguiente pregunta del usuario y determina si solicita un gráfico, una tabla o una respuesta textual/analítica.
                                Si solicita una visualización (gráfico o tabla), extrae el tipo de visualización, las columnas para los ejes X e Y (si es gráfico), una columna para colorear/agrupar (si se pide una segmentación), el período de agregación (día, mes, año, ninguno) y cualquier filtro de fecha o valor.
                                Si solicita una tabla, también especifica las columnas que deben mostrarse en `table_columns`.
                                Si no es una solicitud de visualización (gráfico/tabla), marca 'is_chart_request' como false y 'chart_type' como 'none'.

                                **Prioridades de Respuesta:**
                                1.  **Respuesta Textual/Análisis:** Si la pregunta busca un dato específico (total, promedio, máximo, mínimo), un ranking, una comparación directa, una estimación, una proyección o un análisis descriptivo, prioriza `is_chart_request: false` y proporciona una `summary_response` detallada con los valores calculados y las conclusiones.
                                2.  **Tabla:** Si la pregunta pide 'listar', 'mostrar una tabla', 'detallar', 'qué clientes/productos/categorías' o una vista de datos estructurada, prioriza `is_chart_request: true` y `chart_type: table`. Especifica las columnas relevantes en `table_columns`.
                                3.  **Gráfico:** Si la pregunta pide 'gráfico', 'evolución', 'distribución', 'comparación visual', prioriza `is_chart_request: true` y el `chart_type` adecuado (line, bar, pie, scatter).

                                **Columnas de datos disponibles y sus tipos (usa estos nombres EXACTOS):**
                                {available_columns_str}

                                **Resumen completo del DataFrame (para entender el contexto y los valores):**
                                {df_summary_str}

                                **Consideraciones para la respuesta JSON:**
                                -   `x_axis` y `y_axis`: Nombres de columnas exactos. Vacío si no aplica (para textual o algunas tablas).
                                -   `color_column`: Nombre de columna exacto para segmentación. Vacío si no aplica.
                                -   `filter_column` y `filter_value`: Para filtros específicos (ej: 'Fecha' para '2025', 'TipoCliente' para 'Particular').
                                -   `start_date` y `end_date`: Para rangos de fecha (YYYY-MM-DD).
                                -   `aggregation_period`: **Muy importante.** Debe ser 'day', 'month', 'year' o 'none' según la granularidad solicitada por el usuario o la más lógica para la visualización/análisis. Por ejemplo, "ventas mensuales" -> 'month'. "ventas totales de 2024" -> 'year'. "ventas por cliente" -> 'none' (ya que no es una agregación temporal).
                                -   `table_columns`: Una lista de strings con los nombres exactos de las columnas que deben mostrarse en la tabla. Solo aplica si `chart_type` es `table`. Si es una tabla de resumen (ej. ventas por cliente), incluye las columnas de agrupación y la columna de valor.
                                -   `summary_response`: Una respuesta conversacional amigable que introduce la visualización o el análisis. Para respuestas textuales, debe contener la información solicitada directamente.

                                **Ejemplos de cómo mapear la intención (en formato JSON válido):**
                                -   "evolución de ventas del año 2025": {{"is_chart_request": true, "chart_type": "line", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "Fecha", "filter_value": "2025", "color_column": "", "start_date": "", "end_date": "", "additional_filters": [], "summary_response": "Aquí tienes la evolución de ventas para el año 2025:", "aggregation_period": "month", "table_columns": []}}
                                -   "ventas por mes": {{"is_chart_request": true, "chart_type": "bar", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": "", "additional_filters": [], "summary_response": "Aquí tienes un gráfico de barras de las ventas por mes:", "aggregation_period": "month", "table_columns": []}}
                                -   "gráfico de barras de montos facturados por TipoCliente": {{"is_chart_request": true, "chart_type": "bar", "x_axis": "TipoCliente", "y_axis": "Monto Facturado", "filter_column": "", "filter_value": "", "color_column": "TipoCliente", "start_date": "", "end_date": "", "additional_filters": [], "summary_response": "Aquí tienes un gráfico de barras de los montos facturados por TipoCliente:", "aggregation_period": "none", "table_columns": []}}
                                -   "creame un grafico con la evolucion de ventas de 2025 separado por particular y seguro": {{"is_chart_request": true, "chart_type": "line", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "Fecha", "filter_value": "2025", "color_column": "TipoCliente", "start_date": "", "end_date": "", "additional_filters": [], "summary_response": "Aquí tienes la evolución de ventas de 2025, separada por particular y seguro:", "aggregation_period": "month", "table_columns": []}}
                                -   "ventas entre 2024-03-01 y 2024-06-30": {{"is_chart_request": true, "chart_type": "line", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "2024-03-01", "end_date": "2024-06-30", "additional_filters": [], "summary_response": "Aquí tienes la evolución de ventas entre marzo y junio de 2024:", "aggregation_period": "month", "table_columns": []}}
                                -   "ventas de particular en el primer trimestre de 2025": {{"is_chart_request": true, "chart_type": "line", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "Fecha", "filter_value": "2025", "color_column": "", "start_date": "2025-01-01", "end_date": "2025-03-31", "additional_filters": [{{"column": "TipoCliente", "value": "particular"}}], "summary_response": "Aquí tienes las ventas de clientes particulares en el primer trimestre de 2025:", "aggregation_period": "month", "table_columns": []}}
                                -   "analisis de mis ingresos": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Analizando tus ingresos, se observa...", "aggregation_period": "none", "table_columns": []}}
                                -   "qué cliente vendía más": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Basado en tus datos, el cliente que generó la mayor cantidad de ventas es 'Cliente X' con un total de $Y. Esto representa el Z% del total de tus ventas.", "aggregation_period": "none", "table_columns": []}}
                                -   "dame el total de ventas": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "El monto total facturado en todos los datos es de ${total_monto_facturado:.2f}.", "aggregation_period": "none", "table_columns": []}}
                                -   "cuál fue el mes con menos ingresos": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "El mes con menos ingresos fue {mes_min_ingresos} con un total de ${monto_min_ingresos:.2f}.", "aggregation_period": "none", "table_columns": []}}
                                -   "hazme una estimacion de como sera el mes de agosto dada las ventas de 2025": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Aquí tienes una estimación de las ventas para agosto de 2025: [Tu estimación basada en el análisis de tendencias].", "aggregation_period": "none", "table_columns": []}}
                                -   "muéstrame una tabla de los montos facturados por cliente": {{"is_chart_request": true, "chart_type": "table", "x_axis": "TipoCliente", "y_axis": "Monto Facturado", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Aquí tienes una tabla con los montos facturados por TipoCliente:", "aggregation_period": "none", "table_columns": ["TipoCliente", "Monto Facturado"]}}
                                -   "lista las ventas de cada tipo de cliente": {{"is_chart_request": true, "chart_type": "table", "x_axis": "TipoCliente", "y_axis": "Monto Facturado", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Aquí tienes una tabla con las ventas por TipoCliente:", "aggregation_period": "none", "table_columns": ["TipoCliente", "Monto Facturado"]}}
                                -   "ventas mensuales de 2023": {{"is_chart_request": true, "chart_type": "line", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "Fecha", "filter_value": "2023", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Aquí tienes las ventas mensuales de 2023:", "aggregation_period": "month", "table_columns": []}}
                                -   "ventas por año": {{"is_chart_request": true, "chart_type": "bar", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Aquí tienes las ventas agrupadas por año:", "aggregation_period": "year", "table_columns": []}}
                                -   "total facturado en 2024": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "Fecha", "filter_value": "2024", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "El monto total facturado en 2024 fue de ${total_2024:.2f}.", "aggregation_period": "year", "table_columns": []}}

                                **Pregunta del usuario:** "{pregunta}"
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
                                "description": "True si el usuario pide un gráfico o tabla, false en caso contrario."
                            },
                            "chart_type": {
                                "type": "STRING",
                                "enum": ["line", "bar", "pie", "scatter", "table", "none"],
                                "description": "Tipo de visualización (line, bar, pie, scatter, table). 'none' si no es una visualización o tipo no claro."
                            },
                            "x_axis": {
                                "type": "STRING",
                                "description": "Nombre de la columna para el eje X (ej: 'Fecha'). Vacío si no es gráfico."
                            },
                            "y_axis": {
                                "type": "STRING",
                                "description": "Nombre de la columna para el eje Y (ej: 'Monto Facturado'). Vacío si no es gráfico."
                            },
                            "color_column": {
                                "type": "STRING",
                                "description": "Nombre de la columna para colorear/agrupar (ej: 'TipoCliente'). Vacío si no se pide segmentación o la columna no existe."
                            },
                            "filter_column": {
                                "type": "STRING",
                                "description": "Columna para filtro principal (ej: 'Fecha' para año). Vacío si no hay filtro principal."
                            },
                            "filter_value": {
                                "type": "STRING",
                                "description": "Valor para filtro principal (ej: '2025', 'Enero'). Vacío si no hay filtro principal."
                            },
                            "start_date": {
                                "type": "STRING",
                                "description": "Fecha de inicio del rango (YYYY-MM-DD). Vacío si no hay rango."
                            },
                            "end_date": {
                                "type": "STRING",
                                "description": "Fecha de fin del rango (YYYY-MM-DD). Vacío si no hay rango."
                            },
                            "additional_filters": {
                                "type": "ARRAY",
                                "description": "Lista de filtros adicionales por columna.",
                                "items": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "column": {"type": "STRING"},
                                        "value": {"type": "STRING"}
                                    }
                                }
                            },
                            "summary_response": {
                                "type": "STRING",
                                "description": "Respuesta conversacional si se genera un gráfico o tabla. Vacío si no es gráfico/tabla."
                            },
                            "aggregation_period": { # Nuevo campo para granularidad de tiempo
                                "type": "STRING",
                                "enum": ["day", "month", "year", "none"],
                                "description": "Período de agregación para datos de tiempo (day, month, year) o 'none' si no aplica."
                            },
                            "table_columns": { # Nuevo campo para columnas de tabla
                                "type": "ARRAY",
                                "items": {"type": "STRING"},
                                "description": "Lista de nombres de columnas a mostrar en una tabla. Solo aplica si chart_type es 'table'."
                            }
                        },
                        "required": ["is_chart_request", "chart_type", "x_axis", "y_axis", "color_column", 
                                     "filter_column", "filter_value", "start_date", "end_date", 
                                     "additional_filters", "summary_response", "aggregation_period", "table_columns"]
                    }
                }
            }

            try:
                with st.spinner("Analizando su solicitud y preparando la visualización/análisis..."):
                    chart_response = requests.post(api_url, headers={"Content-Type": "application/json"}, json=chart_detection_payload)
                    if chart_response.status_code == 200:
                        chart_response_json = chart_response.json()
                        if chart_response_json and "candidates" in chart_response_json and \
                           len(chart_response_json["candidates"]) > 0 and \
                           "content" in chart_response_json["candidates"][0] and \
                           "parts" in chart_response_json["candidates"][0]["content"] and \
                           len(chart_response_json["candidates"][0]["content"]["parts"]) > 0:

                            chart_data_raw = chart_response_json["candidates"][0]["content"]["parts"][0]["text"]
                            try:
                                chart_data = json.loads(chart_data_raw)
                            except json.JSONDecodeError as e:
                                st.error(f"❌ Error al procesar la respuesta JSON del modelo. El modelo devolvió JSON inválido: {e}")
                                st.text(f"Respuesta cruda del modelo: {chart_data_raw}")
                                st.stop()
                        else:
                            st.error("❌ La respuesta del modelo no contiene la estructura esperada para la detección de visualización.")
                            st.text(f"Respuesta completa: {chart_response.text}")
                            st.stop()
                    else:
                        st.error(f"❌ Error al consultar Gemini API para detección de visualización: {chart_response.status_code}")
                        st.text(chart_response.text)
                        st.stop()

                    if chart_data.get("is_chart_request"):
                        st.success(chart_data.get("summary_response", "Aquí tienes la visualización solicitada:"))

                        filtered_df = df.copy()

                        # --- Aplicar filtro principal (año/mes) ---
                        if chart_data["filter_column"] and chart_data["filter_value"]:
                            if chart_data["filter_column"] == "Fecha":
                                try:
                                    year_to_filter = int(chart_data["filter_value"])
                                    filtered_df = filtered_df[filtered_df["Fecha"].dt.year == year_to_filter]
                                except ValueError:
                                    # Intentar filtrar por mes si no es un año
                                    month_name = chart_data["filter_value"].lower()
                                    month_map = {
                                        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
                                        'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
                                        'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
                                    }
                                    if month_name in month_map:
                                        filtered_df = filtered_df[filtered_df["Fecha"].dt.month == month_map[month_name]]
                                    else:
                                        st.warning(f"No se pudo aplicar el filtro de fecha '{chart_data['filter_value']}'.")
                            else: # Filtrar por otras columnas de texto/numéricas
                                if chart_data["filter_column"] in filtered_df.columns:
                                    filtered_df = filtered_df[filtered_df[chart_data["filter_column"]].astype(str).str.contains(chart_data["filter_value"], case=False, na=False)]
                                else:
                                    st.warning(f"La columna '{chart_data['filter_column']}' para filtro principal no se encontró.")


                        # --- Aplicar filtros por rango de fechas (start_date, end_date) ---
                        if chart_data.get("start_date"):
                            try:
                                start_dt = pd.to_datetime(chart_data["start_date"])
                                filtered_df = filtered_df[filtered_df["Fecha"] >= start_dt]
                            except ValueError:
                                st.warning(f"Formato de fecha de inicio inválido: {chart_data['start_date']}. No se aplicó el filtro.")
                        if chart_data.get("end_date"):
                            try:
                                end_dt = pd.to_datetime(chart_data["end_date"])
                                filtered_df = filtered_df[filtered_df["Fecha"] <= end_dt]
                            except ValueError:
                                st.warning(f"Formato de fecha de fin inválido: {chart_data['end_date']}. No se aplicó el filtro.")

                        # --- Aplicar filtros adicionales ---
                        if chart_data.get("additional_filters"):
                            for add_filter in chart_data["additional_filters"]:
                                col = add_filter.get("column")
                                val = add_filter.get("value")
                                if col and val and col in filtered_df.columns:
                                    filtered_df = filtered_df[filtered_df[col].astype(str).str.contains(val, case=False, na=False)]
                                elif col and col not in filtered_df.columns:
                                    st.warning(f"La columna '{col}' para filtro adicional no se encontró en los datos.")


                        # Asegurarse de que haya datos después de filtrar
                        if filtered_df.empty:
                            st.warning("No hay datos para generar la visualización con los filtros especificados.")
                        else:
                            x_col = chart_data.get("x_axis")
                            y_col = chart_data.get("y_axis")
                            color_col = chart_data.get("color_column")
                            aggregation_period = chart_data.get("aggregation_period", "none") # Nuevo: obtener período de agregación
                            table_columns = chart_data.get("table_columns", []) # Nuevo: obtener columnas para tabla

                            # Asegurarse de que color_col sea None si es una cadena vacía
                            if color_col == "":
                                color_col = None

                            # Validar que las columnas existan en el DataFrame antes de usarlas
                            # La validación de x_col/y_col solo es estrictamente necesaria para gráficos
                            # Para tablas, la lógica de display puede ser más flexible
                            if chart_data["chart_type"] != "table": 
                                if x_col and x_col not in filtered_df.columns:
                                    st.error(f"La columna '{x_col}' para el eje X no se encontró en los datos. Por favor, revisa el nombre de la columna en tu hoja de cálculo.")
                                    st.stop()
                                if y_col and y_col not in filtered_df.columns:
                                    st.error(f"La columna '{y_col}' para el eje Y no se encontró en los datos. Por favor, revisa el nombre de la columna en tu hoja de cálculo.")
                                    st.stop()
                            
                            # Si color_col no es None y no está en las columnas, advertir y establecer a None
                            if color_col is not None and color_col not in filtered_df.columns:
                                st.warning(f"La columna '{color_col}' para segmentación no se encontró en los datos. El gráfico no se segmentará. Por favor, revisa el nombre de la columna en tu hoja de cálculo.")
                                color_col = None # Ignorar la columna si no existe

                            # --- Lógica de Agregación y Visualización ---
                            fig = None
                            if chart_data["chart_type"] in ["line", "bar"]:
                                group_cols = []
                                x_col_for_plot = x_col # Por defecto, el nombre original de la columna X

                                if x_col == "Fecha" and aggregation_period != "none":
                                    # Agrupar por el período que tenga sentido
                                    if aggregation_period == "month":
                                        filtered_df['Fecha_Agrupada'] = filtered_df['Fecha'].dt.to_period('M').dt.to_timestamp()
                                    elif aggregation_period == "year":
                                        filtered_df['Fecha_Agrupada'] = filtered_df['Fecha'].dt.to_period('Y').dt.to_timestamp()
                                    elif aggregation_period == "day":
                                        filtered_df['Fecha_Agrupada'] = filtered_df['Fecha'].dt.normalize() # Agrupar por día exacto
                                    
                                    group_cols.append('Fecha_Agrupada')
                                    x_col_for_plot = 'Fecha_Agrupada'
                                else:
                                    # Si no es fecha o no hay agregación temporal, usar x_col directamente
                                    if x_col: # Asegurarse de que x_col no esté vacío
                                        group_cols.append(x_col)
                                    
                                if color_col:
                                    group_cols.append(color_col)

                                # Asegurarse de que y_col es numérico para la suma
                                if pd.api.types.is_numeric_dtype(filtered_df[y_col]):
                                    # Solo agrupar si hay columnas para agrupar
                                    if group_cols:
                                        aggregated_df = filtered_df.groupby(group_cols, as_index=False)[y_col].sum()
                                    else: # Si no hay columnas para agrupar, simplemente usar el df filtrado
                                        aggregated_df = filtered_df.copy()

                                    # Ordenar si es una columna de fecha agrupada
                                    if x_col_for_plot == 'Fecha_Agrupada':
                                        aggregated_df = aggregated_df.sort_values(by='Fecha_Agrupada')
                                    elif x_col and x_col in aggregated_df.columns: # Ordenar por x_col si existe en el df agregado
                                        aggregated_df = aggregated_df.sort_values(by=x_col)
                                else:
                                    st.warning(f"La columna '{y_col}' no es numérica y no se puede sumar para el gráfico. Mostrando datos sin agregar.")
                                    aggregated_df = filtered_df.copy()
                                    x_col_for_plot = x_col # Usar x_col original

                                if chart_data["chart_type"] == "line":
                                    fig = px.line(aggregated_df, x=x_col_for_plot, y=y_col, color=color_col,
                                                  title=f"Evolución de {y_col} por {x_col}",
                                                  labels={x_col_for_plot: x_col, y_col: y_col})
                                elif chart_data["chart_type"] == "bar":
                                    fig = px.bar(aggregated_df, x=x_col_for_plot, y=y_col, color=color_col,
                                                 title=f"Distribución de {y_col} por {x_col}",
                                                 labels={x_col_for_plot: x_col, y_col: y_col})

                            elif chart_data["chart_type"] == "pie":
                                # Para gráficos de pastel, agrupar por x_col y sumar y_col
                                if x_col and y_col and x_col in filtered_df.columns and y_col in filtered_df.columns:
                                    if pd.api.types.is_numeric_dtype(filtered_df[y_col]):
                                        grouped_pie_df = filtered_df.groupby(x_col)[y_col].sum().reset_index()
                                        fig = px.pie(grouped_pie_df, names=x_col, values=y_col,
                                                     title=f"Proporción de {y_col} por {x_col}")
                                    else:
                                        st.warning(f"La columna '{y_col}' no es numérica para el gráfico de pastel. Mostrando el DataFrame filtrado.")
                                        st.dataframe(filtered_df)
                                else:
                                    st.warning("Columnas necesarias para el gráfico de pastel no encontradas. Mostrando el DataFrame filtrado.")
                                    st.dataframe(filtered_df)

                            elif chart_data["chart_type"] == "scatter":
                                # Para scatter, no se agrega, se usan los datos filtrados directamente
                                if x_col and y_col and x_col in filtered_df.columns and y_col in filtered_df.columns:
                                    fig = px.scatter(filtered_df, x=x_col, y=y_col, color=color_col,
                                                     title=f"Relación entre {x_col} y {y_col}",
                                                     labels={x_col: x_col, y_col: y_col})
                                else:
                                    st.warning("Columnas necesarias para el gráfico de dispersión no encontradas. Mostrando el DataFrame filtrado.")
                                    st.dataframe(filtered_df)

                            elif chart_data["chart_type"] == "table":
                                st.subheader(chart_data.get("summary_response", "Aquí tienes la tabla solicitada:"))
                                
                                # Si Gemini especificó columnas para la tabla, usarlas
                                if table_columns:
                                    # Validar que las columnas existan en el DataFrame filtrado
                                    valid_table_columns = [col for col in table_columns if col in filtered_df.columns]
                                    if len(valid_table_columns) == len(table_columns):
                                        st.dataframe(filtered_df[valid_table_columns])
                                    else:
                                        st.warning(f"Algunas columnas solicitadas para la tabla no se encontraron: {', '.join(set(table_columns) - set(filtered_df.columns))}. Mostrando el DataFrame filtrado completo.")
                                        st.dataframe(filtered_df)
                                # Si no especificó, o si x_col/y_col están presentes, intentar una tabla agregada
                                elif x_col and y_col and x_col in filtered_df.columns and y_col in filtered_df.columns:
                                    table_group_cols = [x_col]
                                    if color_col and color_col in filtered_df.columns:
                                        table_group_cols.append(color_col)
                                    
                                    # Agregación para la tabla si es numérica
                                    if pd.api.types.is_numeric_dtype(filtered_df[y_col]):
                                        table_data = filtered_df.groupby(table_group_cols)[y_col].sum().reset_index()
                                        st.dataframe(table_data)
                                    else:
                                        st.warning(f"La columna '{y_col}' no es numérica para agregar en la tabla. Mostrando el DataFrame filtrado completo.")
                                        st.dataframe(filtered_df)
                                else: # Si no hay columnas específicas o x_col/y_col, mostrar el DataFrame filtrado completo
                                    st.dataframe(filtered_df)
                                
                                fig = "handled_as_table" # Marcar como manejado para no intentar plotear

                            if fig and fig != "handled_as_table":
                                st.plotly_chart(fig, use_container_width=True)
                            elif fig is None and chart_data["chart_type"] != "table": # Si no se generó ni gráfico ni tabla, y no es una tabla
                                st.warning("No se pudo generar la visualización solicitada o los datos no son adecuados.")
                    else: # Si no es una solicitud de gráfico/tabla, procede con el análisis de texto
                        # Solo muestra el summary_response si is_chart_request es false y hay un summary_response
                        if chart_data.get("summary_response"):
                            st.success("🤖 Respuesta de Gemini:")
                            st.write(chart_data.get("summary_response"))
                        else:
                            # --- SEGUNDA LLAMADA A GEMINI: ANÁLISIS Y RECOMENDACIONES (con mejoras) ---
                            contexto_analisis = f"""Eres un asesor financiero impecable. Tu misión es ayudar al usuario a interpretar sus datos, identificar tendencias, predecir posibles escenarios (con cautela) y ofrecer recomendaciones estratégicas.

                            **Resumen completo del DataFrame (para tu análisis):**
                            {df_summary_str}

                            **Columnas de datos disponibles y sus tipos (usa estos nombres EXACTOS):**
                            {available_columns_str}

                            Basándote **exclusivamente** en la información proporcionada en el resumen del DataFrame y en tu rol de analista financiero, por favor, responde a la siguiente pregunta del usuario.

                            Al formular tu respuesta, considera lo siguiente:
                            1.  **Análisis Profundo:** Busca patrones, anomalías, crecimientos o decrecimientos significativos. Identifica y destaca cualquier punto clave (máximos, mínimos, cambios abruptos) relevantes para la pregunta. Si es posible, menciona métricas clave o porcentajes de cambio.
                            2.  **Cálculos Explícitos:** Si la pregunta implica un cálculo (total, promedio, máximo, mínimo, etc.), realiza el cálculo mentalmente (basado en el df_summary_str o en tu conocimiento general de cómo se calcularía con esos datos) y proporciona el resultado numérico directamente en tu respuesta textual.
                            3.  **Predicción (si aplica):** Si la pregunta sugiere una proyección, basa tu estimación en las tendencias históricas visibles en los datos. **IMPORTANTE: Siempre aclara que cualquier predicción es una estimación basada en datos pasados y no una garantía ni un consejo financiero.**
                            4.  **Recomendaciones Accionables:** Ofrece consejos prácticos y accionables que el usuario pueda considerar para mejorar su situación financiera, siempre fundamentados en el análisis de los datos.
                            5.  **Tono:** Mantén un tono profesional, claro, conciso y empático.
                            6.  **Idioma:** Responde siempre en español.
                            7.  **Orden y Claridad:** Estructura tu respuesta con encabezados o puntos clave para facilitar la lectura.

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

            except requests.exceptions.Timeout:
                st.error("❌ La solicitud a la API de Gemini ha excedido el tiempo de espera (timeout). Esto puede ser un problema de red o que el servidor de Gemini esté tardando en responder.")
            except requests.exceptions.ConnectionError:
                st.error("❌ Error de conexión a la API de Gemini. Verifica tu conexión a internet o si la URL de la API es correcta.")
            except json.JSONDecodeError:
                st.error("❌ Error al procesar la respuesta JSON del modelo. Intente de nuevo o reformule la pregunta.")
                st.text(chart_response.text if 'chart_response' in locals() else "No se pudo obtener una respuesta.")
            except Exception as e:
                st.error("❌ Falló la conexión con la API de Gemini o hubo un error inesperado.")
                st.exception(e)

    except Exception as e:
        st.error("❌ No se pudo cargar la hoja de cálculo.")
        st.exception(e)
