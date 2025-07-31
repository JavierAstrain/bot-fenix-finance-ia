import streamlit as st
import pandas as pd
import gspread
import json
import requests
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime
import numpy as np
from statsmodels.tsa.seasonal import seasonal_decompose # Para descomposición de series de tiempo
from dateutil.relativedelta import relativedelta # Para añadir meses fácilmente
from io import StringIO # Para capturar la salida de df.info()

# --- Configuración de Login ---
USERNAME = "javi"
PASSWORD = "javi"

# Inicializar el estado de la sesión para el login y las hojas
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "question_history" not in st.session_state:
    st.session_state.question_history = []
if "dfs" not in st.session_state:
    st.session_state.dfs = {}
if "selected_sheet" not in st.session_state:
    st.session_state.selected_sheet = None


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
                # Recargar la página para mostrar la aplicación completa
                st.experimental_rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")

# Mostrar el formulario de login si el usuario no ha iniciado sesión
if not st.session_state.logged_in:
    show_login_form()
else:
    # --- AGREGAR LOGO DE LA EMPRESA Y TÍTULO ---
    col_title, col_logo = st.columns([0.7, 0.3]) # 70% para título, 30% para logo

    with col_title:
        st.title("🤖 Bot Fénix Finance IA")

    with col_logo:
        try:
            st.image("logo_high_resolution.jpg", width=150) # Ajusta el ancho según sea necesario
        except FileNotFoundError:
            st.warning("No se encontró el archivo 'logo_high_resolution.jpg'. Asegúrate de que esté en la misma carpeta.")

    st.write("Haz preguntas en lenguaje natural sobre tu información financiera.")

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


    # --- CARGA DATOS DESDE GOOGLE SHEET (AHORA PARA MÚLTIPLES HOJAS) ---
    # Reemplaza '1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk' con el ID de tu planilla.
    SPREADSHEET_ID = "1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk"
    
    # Define los nombres EXACTOS de tus hojas de cálculo aquí.
    hojas_a_cargar = ['Facturacion', 'Reparacion', 'Recepcion', 'Otra Hoja']

    @st.cache_data(ttl=600)  # Caching de los datos por 10 minutos
    def load_data(sheet_id, sheet_names):
        """
        Carga los datos de múltiples hojas de cálculo y los preprocesa.
        """
        try:
            spreadsheet = client.open_by_key(sheet_id)
            dfs = {}
            for sheet_name in sheet_names:
                try:
                    worksheet = spreadsheet.worksheet(sheet_name)
                    data = worksheet.get_all_values()
                    df = pd.DataFrame(data[1:], columns=data[0])
                    
                    # --- Limpieza y conversión de datos ---
                    df.columns = df.columns.str.strip()
                    if 'Fecha' in df.columns:
                        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
                    
                    if 'Monto Facturado' in df.columns:
                        df['Monto Facturado'] = df['Monto Facturado'].astype(str).str.replace('[$,.]', '', regex=True).str.replace(',', '.', regex=False)
                        df['Monto Facturado'] = pd.to_numeric(df['Monto Facturado'], errors="coerce")

                    numeric_cols_other = ['Materiales y Pintura', 'Costos Financieros', 'Descuento Aplicado (%)']
                    for col in numeric_cols_other:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors="coerce")

                    df.dropna(subset=["Fecha"], inplace=True)
                    dfs[sheet_name] = df

                except gspread.WorksheetNotFound:
                    st.warning(f"⚠️ La hoja '{sheet_name}' no se encontró. Revisa el nombre.")
                except Exception as e:
                    st.error(f"❌ Error al procesar la hoja '{sheet_name}': {e}")
            
            return dfs
        except Exception as e:
            st.error("❌ Error al cargar la planilla completa. Revisa el ID y permisos.")
            st.exception(e)
            return {}

    # Cargar los datos y almacenarlos en el estado de la sesión
    st.session_state.dfs = load_data(SPREADSHEET_ID, hojas_a_cargar)

    if not st.session_state.dfs:
        st.error("No se pudo cargar ninguna hoja de cálculo. La aplicación se detendrá.")
        st.stop()

    # --- SELECCIONAR LA HOJA A ANALIZAR ---
    st.subheader("Selecciona la Hoja de Cálculo a Analizar")
    st.session_state.selected_sheet = st.selectbox(
        "Elige una hoja de tu planilla para interactuar:",
        options=list(st.session_state.dfs.keys()),
        index=list(st.session_state.dfs.keys()).index(st.session_state.selected_sheet) if st.session_state.selected_sheet in st.session_state.dfs else 0
    )

    df = st.session_state.dfs[st.session_state.selected_sheet]

    # --- AHORA CONTINÚA CON EL CÓDIGO ORIGINAL, PERO USANDO 'df' ---
    # El resto de tu lógica para verificar columnas, mostrar vista previa,
    # generar el prompt para Gemini y la interacción del usuario se mantiene igual.

    # --- Verificación de columnas esenciales al inicio (con los nombres exactos del usuario) ---
    required_columns = ["Fecha", "Cliente", "Tipo Cliente", "Tipo Vehículo", "Factura N°", "Monto Facturado", "Materiales y Pintura", "Costos Financieros", "Sucursal", "Ejecutivo", "Estado Pago", "Forma de Pago", "Descuento Aplicado (%)", "Observaciones"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        st.warning(f"⚠️ La hoja '{st.session_state.selected_sheet}' no contiene todas las columnas esenciales para un análisis completo: {', '.join(missing_columns)}. Algunas funcionalidades podrían no estar disponibles.")

    # --- Verificar si el DataFrame está vacío después de la limpieza ---
    if df.empty:
        st.error(f"⚠️ La hoja seleccionada '{st.session_state.selected_sheet}' no contiene datos válidos después de la limpieza.")
        # Aquí no detenemos la app, solo mostramos el error y continuamos para que el usuario pueda cambiar de hoja.

    # --- Mostrar vista previa de los datos después de la carga y limpieza ---
    st.subheader(f"📊 Vista previa de los datos de la hoja: '{st.session_state.selected_sheet}'")
    st.dataframe(df.head(10))

    # --- Generar información dinámica de columnas para el prompt de Gemini ---
    available_columns_info = []
    if not df.empty:
        for col in df.columns:
            col_type = df[col].dtype
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                min_date = df[col].min()
                max_date = df[col].max()
                if pd.isna(min_date) or pd.isna(max_date):
                    available_columns_info.append(f"- '{col}' (tipo fecha, formato YYYY-MM-DD, con valores nulos)")
                else:
                    available_columns_info.append(f"- '{col}' (tipo fecha, formato YYYY-MM-DD, rango: {min_date.strftime('%Y-%m-%d')} a {max_date.strftime('%Y-%m-%d')})")
            elif pd.api.types.is_numeric_dtype(df[col]):
                available_columns_info.append(f"- '{col}' (tipo numérico)")
            else:
                unique_vals = df[col].dropna().unique()
                if len(unique_vals) < 10:
                    available_columns_info.append(f"- '{col}' (tipo texto, valores: {', '.join(map(str, unique_vals))})")
                else:
                    available_columns_info.append(f"- '{col}' (tipo texto)")
    available_columns_str = "\n".join(available_columns_info)

    # --- Generar un resumen más completo del DataFrame para Gemini ---
    df_summary_parts = []
    if not df.empty:
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
                col_info += f" Estadísticas: Min={df[col].min():,.2f}, Max={df[col].max():,.2f}, Media={df[col].mean():,.2f}, Suma={df[col].sum():,.2f}"
            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                min_date = df[col].min()
                max_date = df[col].max()
                if not pd.isna(min_date) and not pd.isna(max_date):
                    col_info += f" Rango de fechas: [{min_date.strftime('%Y-%m-%d')} a {max_date.strftime('%Y-%m-%d')}]"
                else:
                    col_info += " Rango de fechas: (Contiene valores nulos o inválidos)"
            elif pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
                top_values_counts = df[col].value_counts().nlargest(10)
                if not top_values_counts.empty:
                    top_values_str = [f"'{val}' ({count})" for val, count in top_values_counts.items()]
                    col_info += f" Valores más frecuentes: {', '.join(top_values_str)}"
            df_summary_parts.append(col_info)
    else:
        df_summary_parts.append("La hoja seleccionada no contiene datos.")
            
    df_summary_str = "\n".join(df_summary_parts)


    # --- Sección de "Qué puedes preguntar" ---
    with st.expander("💡 ¿Qué puedes preguntar y cuáles son los alcances de este bot?"):
        st.write("""
        Este bot de Fénix Finance IA está diseñado para ayudarte a analizar tus datos financieros. Puedes:

        * **Consultar Datos Específicos y Generar Tablas:**
            * Ej: "¿Cuál fue el Monto Facturado total en el mes de marzo de 2025?"
            * Ej: "**Muéstrame una tabla** con los Montos Facturados por cada Tipo Cliente."
            * Ej: "**Lista** las 5 transacciones con mayor Monto Facturado."
            * Ej: "Dime el total de ventas para el Tipo Cliente 'Particular' en 2024."

        * **Realizar Cálculos Financieros:**
            * Ej: "¿Cuál es la variación porcentual en cuanto a costos financieros entre el año 2023 y 2024?"
            * Ej: "Calcula el promedio de 'Monto Facturado' por 'Sucursal'."
            * Ej: "Cuál es el total de 'Materiales y Pintura' para el año 2024?"
            * **Ej: "Qué porcentaje de venta corresponde a particular?"**
            * **Ej: "Dame el porcentaje de ventas de pesado."**

        * **Generar Gráficos Interactivos:**
            * **Evolución:** "Hazme un gráfico de línea con la evolución de Monto Facturado en 2023."
            * **Comparación:** "Muestra un gráfico de barras del Monto Facturado por mes."
            * **Segmentación:** "Crea un gráfico de evolución de ventas de 2025 separado por Tipo Cliente."
            * **Rangos de Fecha:** "Gráfico de Monto Facturado entre 2024-01-15 y 2024-04-30."
            * **Tipos de Gráfico:** Línea, barras, pastel, dispersión.

        * **Realizar Análisis y Obtener Perspectivas:**
            * Ej: "¿Qué tendencias observas en mis Montos Facturados?"
            * Ej: "¿Hubo alguna anomalía en las ventas del último trimestre?"
            * Ej: "Dame un análisis de los datos de 2024."
            * Ej: "¿Cuál es el cliente que genera mayor cantidad de ventas?"
            * **Ej: "¿Cómo puedo mejorar las ventas de lo que queda del 2025?"**

        * **Hacer Estimaciones y Proyecciones (con cautela y estacionalidad):**
            * Ej: "¿Podrías proyectar el Monto Facturado para el próximo mes basándote en los datos históricos?"
            * **Ej: "Hazme una estimación de la venta para lo que queda de 2025 por mes, considerando estacionalidades."**
            * **Alcance:** Las proyecciones se basan en los datos históricos proporcionados y utilizan modelos de series de tiempo para intentar capturar estacionalidades. **No son consejos financieros garantizados y su precisión depende de la calidad y extensión de tus datos históricos.**

        * **Recibir Recomendaciones Estratégicas:**
            * Ej: "¿Qué recomendaciones me darías para mejorar mi Monto Facturado?"
            * **Alcance:** Las recomendaciones se derivan del análisis de tus datos y buscan ofrecer ideas accionables. **Siempre consulta con un profesional financiero antes de tomar decisiones importantes.**

        **Importante:**
        * El bot solo puede analizar la información presente en la hoja de cálculo **seleccionada**.
        * Asegúrate de que los nombres de las columnas que mencionas en tus preguntas (ej. 'Fecha', 'Monto Facturado', 'Tipo Cliente') coincidan **exactamente** con los de tu hoja.
        * Para análisis avanzados o gráficos segmentados, es necesario que las columnas relevantes existan en tus datos.
        * **Para proyecciones con estacionalidad, se recomienda tener al menos 2-3 años de datos mensuales históricos.**
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
                        test_response = requests.post(test_api_url, headers={"Content-Type": "application/json"}, json=test_payload, timeout=10)
                    
                    st.subheader("Resultado de la Prueba:")
                    st.write(f"Código de estado HTTP: {test_response.status_code}")
                    st.json(test_response.json())

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
    consultar_button = st.button("Consultar")

    if consultar_button and pregunta:
        # Add current question to history
        st.session_state.question_history.append(pregunta)
        # Keep only the last 5 questions
        st.session_state.question_history = st.session_state.question_history[-5:]

        if df.empty:
            st.warning("No se pueden realizar consultas porque la hoja seleccionada no contiene datos.")
            st.stop()

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
                            
                            **Nota Importante:** Estás analizando la hoja de cálculo llamada '{st.session_state.selected_sheet}'.

                            **Prioridades de Respuesta:**
                            1.  **Respuesta Textual/Análisis:** Si la pregunta busca un dato específico (total, promedio, máximo, mínimo), un ranking, una comparación directa, una estimación, una proyección o un análisis descriptivo, prioriza `is_chart_request: false` y proporciona una `summary_response` detallada.
                            2.  **Tabla:** Si la pregunta pide 'listar', 'mostrar una tabla', 'detallar', 'qué clientes/productos/categorías' o una vista de datos estructurada, prioriza `is_chart_request: true` y `chart_type: table`. Especifica las columnas relevantes en `table_columns`.
                            3.  **Gráfico:** Si la pregunta pide 'gráfico', 'evolución', 'distribución', 'comparación visual', prioriza `is_chart_request: true` y el `chart_type` adecuado (line, bar, pie, scatter).

                            **Columnas de datos disponibles y sus tipos (usa estos nombres EXACTOS):**
                            {available_columns_str}

                            **Resumen completo del DataFrame (para entender el contexto y los valores):**
                            {df_summary_str}

                            **Consideraciones para la respuesta JSON (todos los campos son obligatorios):**
                            -   `is_chart_request`: Booleano. True si el usuario pide un gráfico o tabla, false en caso contrario.
                            -   `chart_type`: String. Tipo de visualización (line, bar, pie, scatter, table). 'none' if not a visualization or unclear type.
                            -   `x_axis`: String. Nombre de la columna para el eje X (ej: 'Fecha'). Vacío si no es gráfico.
                            -   `y_axis`: String. Nombre de la columna para el eje Y (ej: 'Monto Facturado'). Vacío si no es gráfico.
                            -   `color_column`: String. Nombre de la columna para colorear/agrupar (ej: 'Tipo Cliente'). Vacío si no se pide segmentación o la columna no existe.
                            -   `filter_column`: String. Columna para filtro principal (ej: 'Fecha' para año). Vacío si no hay filtro principal.
                            -   `filter_value`: String. Valor para filtro principal (ej: '2025', 'Enero'). Vacío si no hay filtro principal.
                            -   `start_date`: String. Fecha de inicio del rango (YYYY-MM-DD). Vacío si no hay rango.
                            -   `end_date`: String. Fecha de fin del rango (YYYY-MM-DD). Vacío si no hay rango.
                            -   `additional_filters`: Array de objetos. Lista de filtros adicionales por columna. Cada objeto tiene 'column' (string) y 'value' (string).
                            -   `summary_response`: String. Respuesta conversacional amigable que introduce la visualización o el análisis. Para respuestas textuales, debe contener la información solicitada directamente.
                            -   `aggregation_period`: String. Período de agregación para datos de tiempo (day, month, year) o 'none' si no aplica.
                            -   `table_columns`: Array de strings. Lista de nombres de columnas a mostrar en una tabla. Solo aplica si chart_type es 'table'.
                            -   `calculation_type`: String. Tipo de cálculo a realizar por Python. Enum: 'none', 'total_sales', 'max_client_sales', 'min_month_sales', 'sales_for_period', 'project_remaining_year', 'project_remaining_year_monthly', 'total_overdue_payments', 'percentage_variation', 'average_by_column', 'total_for_column_by_year', 'percentage_of_total_sales_by_category', 'recommendations'.
                            -   `calculation_params`: Objeto JSON. Parámetros para el cálculo (ej: {{"year": 2025}} para 'total_sales_for_year').

                            **Ejemplos de cómo mapear la intención (en formato JSON válido):**
                            -   "evolución de ventas del año 2025": {{"is_chart_request": true, "chart_type": "line", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "Fecha", "filter_value": "2025", "color_column": "", "start_date": "", "end_date": "", "additional_filters": [], "summary_response": "Aquí tienes la evolución de ventas para el año 2025:", "aggregation_period": "month", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                            -   "ventas por mes": {{"is_chart_request": true, "chart_type": "bar", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": "", "additional_filters": [], "summary_response": "Aquí tienes un gráfico de barras de las ventas por mes:", "aggregation_period": "month", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                            -   "gráfico de barras de montos facturados por Tipo Cliente": {{"is_chart_request": true, "chart_type": "bar", "x_axis": "Tipo Cliente", "y_axis": "Monto Facturado", "filter_column": "", "filter_value": "", "color_column": "Tipo Cliente", "start_date": "", "end_date": "", "additional_filters": [], "summary_response": "Aquí tienes un gráfico de barras de los montos facturados por Tipo Cliente:", "aggregation_period": "none", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                            -   "creame un grafico con la evolucion de ventas de 2025 separado por particular y seguro": {{"is_chart_request": true, "chart_type": "line", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "Fecha", "filter_value": "2025", "color_column": "Tipo Cliente", "start_date": "", "end_date": "", "additional_filters": [], "summary_response": "Aquí tienes la evolución de ventas de 2025, separada por particular y seguro:", "aggregation_period": "month", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                            -   "ventas entre 2024-03-01 y 2024-06-30": {{"is_chart_request": true, "chart_type": "line", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "2024-03-01", "end_date": "2024-06-30", "additional_filters": [], "summary_response": "Aquí tienes la evolución de ventas entre marzo y junio de 2024:", "aggregation_period": "month", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                            -   "ventas de particular en el primer trimestre de 2025": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "Fecha", "filter_value": "2025", "color_column": "", "start_date": "2025-01-01", "end_date": "2025-03-31", "additional_filters": [{{"column": "Tipo Cliente", "value": "particular"}}], "summary_response": "Aquí tienes las ventas de clientes particulares en el primer trimestre de 2025:", "aggregation_period": "month", "table_columns": [], "calculation_type": "sales_for_period", "calculation_params": {{"year": 2025, "month": 1}}}}
                            -   "analisis de mis ingresos": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "", "aggregation_period": "none", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                            -   "qué cliente vendía más": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Basado en tus datos, el cliente que generó la mayor cantidad de ventas es [NOMBRE_CLIENTE_MAX_VENTAS] con un total de $[MONTO_MAX_VENTAS].", "aggregation_period": "none", "table_columns": [], "calculation_type": "max_client_sales", "calculation_params": {{}}}}
                            -   "dame el total de ventas": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "El monto total facturado en todos los datos es de $[TOTAL_MONTO_FACTURADO].", "aggregation_period": "none", "table_columns": [], "calculation_type": "total_sales", "calculation_params": {{}}}}
                            -   "cuál fue el mes con menos ingresos": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "El mes con menos ingresos fue [MES_MIN_INGRESOS] con un total de $[MONTO_MIN_INGRESOS].", "aggregation_period": "none", "table_columns": [], "calculation_type": "min_month_sales", "calculation_params": {{}}}}
                            -   "hazme una estimacion de cual seria la venta para lo que queda de 2025": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "Fecha", "filter_value": "2025", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Aquí tienes una estimación de las ventas para lo que queda de [TARGET_YEAR]: $[ESTIMACION_RESTO_YEAR]. Ten en cuenta que esta es una proyección basada en datos históricos y no una garantía financiera.", "aggregation_period": "none", "table_columns": [], "calculation_type": "project_remaining_year", "calculation_params": {{"target_year": 2025}}}}
                            -   "muéstrame una tabla de los montos facturados por cliente": {{"is_chart_request": true, "chart_type": "table", "x_axis": "Cliente", "y_axis": "Monto Facturado", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Aquí tienes una tabla con los montos facturados por Cliente:", "aggregation_period": "none", "table_columns": ["Cliente", "Monto Facturado"], "calculation_type": "none", "calculation_params": {{}}}}
                            -   "lista las ventas de cada tipo de cliente": {{"is_chart_request": true, "chart_type": "table", "x_axis": "Tipo Cliente", "y_axis": "Monto Facturado", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Aquí tienes una tabla con las ventas por Tipo Cliente:", "aggregation_period": "none", "table_columns": ["Tipo Cliente", "Monto Facturado"], "calculation_type": "none", "calculation_params": {{}}}}
                            -   "ventas mensuales de 2023": {{"is_chart_request": true, "chart_type": "line", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "Fecha", "filter_value": "2023", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Aquí tienes las ventas mensuales de 2023:", "aggregation_period": "month", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                            -   "ventas por año": {{"is_chart_request": true, "chart_type": "bar", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Aquí tienes las ventas agrupadas por año:", "aggregation_period": "year", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                            -   "total facturado en 2024": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "Fecha", "filter_value": "2024", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "El monto total facturado en [YEAR] fue de $[CALCULATED_TOTAL_YEAR].", "aggregation_period": "year", "table_columns": [], "calculation_type": "sales_for_period", "calculation_params": {{"year": 2024}}}}
                            -   "ventas de enero 2025": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "Fecha", "filter_value": "Enero", "color_column": "", "start_date": "2025-01-01", "end_date": "2025-01-31", "additional_filters": [], "summary_response": "Las ventas de [MONTH] de [YEAR] fueron de $[CALCULATED_SALES_MONTH_YEAR].", "aggregation_period": "month", "table_columns": [], "calculation_type": "sales_for_period", "calculation_params": {{"year": 2025, "month": 1}}}}
                            -   "cómo puedo mejorar las ventas de lo que queda del 2025": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "", "aggregation_period": "none", "table_columns": [], "calculation_type": "recommendations", "calculation_params": {{}}}}
                            -   "proyección mensual de ventas para lo que queda del año": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "Fecha", "filter_value": "2025", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Aquí tienes una proyección mensual de ventas para lo que queda de [TARGET_YEAR]:", "aggregation_period": "month", "table_columns": [], "calculation_type": "project_remaining_year_monthly", "calculation_params": {{"target_year": 2025}}}}
                            -   "total de ventas por tipo de cliente": {{"is_chart_request": true, "chart_type": "table", "x_axis": "Tipo Cliente", "y_axis": "Monto Facturado", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Aquí tienes el total de ventas por tipo de cliente:", "aggregation_period": "none", "table_columns": ["Tipo Cliente", "Monto Facturado"], "calculation_type": "none", "calculation_params": {{}}}}
                            -   "qué porcentaje de venta corresponde a particular?": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "El porcentaje de venta para el cliente 'particular' es de [PERCENTAJE]%.", "aggregation_period": "none", "table_columns": [], "calculation_type": "percentage_of_total_sales_by_category", "calculation_params": {{"category_column": "Tipo Cliente", "category_value": "Particular"}}}}
                            -   "dame el porcentaje de ventas de pesado": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "El porcentaje de venta para vehículos 'Pesado' es de [PERCENTAJE]%.", "aggregation_period": "none", "table_columns": [], "calculation_type": "percentage_of_total_sales_by_category", "calculation_params": {{"category_column": "Tipo Vehículo", "category_value": "Pesado"}}}}
                            -   "lista las facturas vencidas": {{"is_chart_request": true, "chart_type": "table", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [{{"column": "Estado Pago", "value": "Vencido"}}], "summary_response": "Aquí tienes una tabla con las facturas cuyo estado de pago es 'Vencido':", "aggregation_period": "none", "table_columns": ["Factura N°", "Fecha", "Cliente", "Monto Facturado", "Estado Pago"], "calculation_type": "none", "calculation_params": {{}}}}
                            
                            **Pregunta del usuario:**
                            {pregunta}

                            **Respuesta (en formato JSON):**
                            """
                        }
                    ]
                },
                "generationConfig": {
                    "response_mime_type": "application/json"
                }
            }
            
            with st.spinner("Analizando tu pregunta..."):
                try:
                    response = requests.post(api_url, headers={"Content-Type": "application/json"}, json=chart_detection_payload, timeout=30)
                    response.raise_for_status()
                    intent_json = json.loads(response.json()["candidates"][0]["content"]["parts"][0]["text"])
                except requests.exceptions.RequestException as e:
                    st.error(f"❌ Error de conexión con la API de Gemini: {e}")
                    st.stop()
                except (KeyError, IndexError, json.JSONDecodeError) as e:
                    st.error(f"❌ Error al procesar la respuesta de la API de Gemini: {e}")
                    st.write("Respuesta de la API:", response.text)
                    st.stop()

            # --- SEGUNDA LLAMADA O LÓGICA DE VISUALIZACIÓN BASADA EN LA INTENCIÓN ---
            with st.spinner("Generando tu respuesta..."):
                if intent_json["is_chart_request"]:
                    # --- Lógica para generar gráficos o tablas ---
                    filtered_df = df.copy()

                    # Aplicar filtros de fecha si existen
                    if intent_json.get("start_date") and intent_json.get("end_date"):
                        try:
                            start = datetime.strptime(intent_json["start_date"], "%Y-%m-%d")
                            end = datetime.strptime(intent_json["end_date"], "%Y-%m-%d")
                            filtered_df = filtered_df[(filtered_df["Fecha"] >= start) & (filtered_df["Fecha"] <= end)]
                            if filtered_df.empty:
                                st.warning(f"No se encontraron datos para el rango de fechas {intent_json['start_date']} a {intent_json['end_date']}.")
                        except (ValueError, KeyError):
                            st.warning("No se pudo aplicar el filtro de fecha. Verifica que la columna 'Fecha' existe y está en formato YYYY-MM-DD.")
                    elif intent_json.get("filter_column") == "Fecha" and intent_json.get("filter_value"):
                        try:
                            year = int(intent_json["filter_value"])
                            filtered_df = filtered_df[filtered_df["Fecha"].dt.year == year]
                        except (ValueError, KeyError):
                            pass # No aplicar filtro si el valor no es un año válido o la columna no existe

                    # Aplicar filtros adicionales
                    for filter_item in intent_json.get("additional_filters", []):
                        col = filter_item.get("column")
                        val = filter_item.get("value")
                        if col in filtered_df.columns and val:
                            filtered_df = filtered_df[filtered_df[col].astype(str).str.contains(val, case=False, na=False)]

                    if filtered_df.empty:
                        st.warning("No se encontraron datos después de aplicar los filtros.")
                        st.stop()
                    
                    st.subheader(intent_json["summary_response"])

                    if intent_json["chart_type"] == "table":
                        # Mostrar una tabla
                        table_cols = intent_json.get("table_columns", [])
                        if table_cols:
                            # Si se pide Monto Facturado o similar, agrupar
                            if "Monto Facturado" in table_cols and "Cliente" in table_cols:
                                # Agrupar por Cliente y sumar el monto
                                grouped_df = filtered_df.groupby("Cliente")["Monto Facturado"].sum().reset_index()
                                # Limpiar columnas no necesarias si se pide Monto y Cliente
                                final_df = grouped_df[["Cliente", "Monto Facturado"]]
                                # Ordenar por monto de forma descendente
                                final_df = final_df.sort_values(by="Monto Facturado", ascending=False).reset_index(drop=True)
                                st.dataframe(final_df, use_container_width=True)
                            elif "Monto Facturado" in table_cols and "Tipo Cliente" in table_cols:
                                grouped_df = filtered_df.groupby("Tipo Cliente")["Monto Facturado"].sum().reset_index()
                                final_df = grouped_df[["Tipo Cliente", "Monto Facturado"]]
                                st.dataframe(final_df, use_container_width=True)
                            else:
                                st.dataframe(filtered_df[table_cols], use_container_width=True)
                        else:
                            st.dataframe(filtered_df, use_container_width=True)

                    elif intent_json["chart_type"] in ["line", "bar", "pie", "scatter"]:
                        # Lógica de gráficos con Plotly
                        x_axis = intent_json["x_axis"]
                        y_axis = intent_json["y_axis"]
                        color_column = intent_json.get("color_column")
                        
                        # Manejar la agregación de datos
                        if x_axis == "Fecha" and intent_json.get("aggregation_period"):
                            # Agrupar por mes, año, etc.
                            period = intent_json["aggregation_period"]
                            if period == "month":
                                filtered_df["Periodo"] = filtered_df["Fecha"].dt.to_period('M').astype(str)
                            elif period == "year":
                                filtered_df["Periodo"] = filtered_df["Fecha"].dt.to_period('Y').astype(str)
                            
                            if color_column:
                                # Agrupar por periodo y columna de color
                                grouped_df = filtered_df.groupby(["Periodo", color_column])[y_axis].sum().reset_index()
                                x_col = "Periodo"
                                y_col = y_axis
                                color_col = color_column
                            else:
                                # Agrupar solo por periodo
                                grouped_df = filtered_df.groupby("Periodo")[y_axis].sum().reset_index()
                                x_col = "Periodo"
                                y_col = y_axis
                                color_col = None
                        else:
                            # No hay agregación de tiempo
                            grouped_df = filtered_df.groupby(x_axis)[y_axis].sum().reset_index()
                            x_col = x_axis
                            y_col = y_axis
                            color_col = color_column

                        if grouped_df.empty:
                            st.warning("No hay datos para generar el gráfico después de la agregación.")
                        else:
                            if intent_json["chart_type"] == "line":
                                fig = px.line(grouped_df, x=x_col, y=y_col, color=color_col, markers=True, title=f"Evolución de {y_axis}")
                                fig.update_layout(xaxis_title=x_axis, yaxis_title=y_axis)
                                st.plotly_chart(fig, use_container_width=True)
                            elif intent_json["chart_type"] == "bar":
                                fig = px.bar(grouped_df, x=x_col, y=y_col, color=color_col, title=f"Distribución de {y_axis} por {x_axis}")
                                fig.update_layout(xaxis_title=x_axis, yaxis_title=y_axis)
                                st.plotly_chart(fig, use_container_width=True)
                            elif intent_json["chart_type"] == "pie":
                                # Para gráficos de pastel, el eje Y es la suma
                                fig = px.pie(filtered_df, values=y_axis, names=x_axis, title=f"Distribución de {y_axis} por {x_axis}")
                                st.plotly_chart(fig, use_container_width=True)
                            elif intent_json["chart_type"] == "scatter":
                                fig = px.scatter(grouped_df, x=x_col, y=y_col, color=color_col, title=f"Relación entre {x_axis} y {y_axis}")
                                fig.update_layout(xaxis_title=x_axis, yaxis_title=y_axis)
                                st.plotly_chart(fig, use_container_width=True)

                else:
                    # --- Lógica para respuestas textuales y cálculos ---
                    calculation_type = intent_json.get("calculation_type", "none")
                    calculation_params = intent_json.get("calculation_params", {})
                    response_text = intent_json["summary_response"]
                    
                    if calculation_type == "total_sales":
                        total = df["Monto Facturado"].sum()
                        response_text = response_text.replace("[TOTAL_MONTO_FACTURADO]", f"{total:,.0f}")
                        st.success(response_text)
                    
                    elif calculation_type == "max_client_sales":
                        # Agrupar por cliente y sumar ventas
                        client_sales = df.groupby("Cliente")["Monto Facturado"].sum().reset_index()
                        max_client = client_sales.loc[client_sales["Monto Facturado"].idxmax()]
                        
                        response_text = response_text.replace("[NOMBRE_CLIENTE_MAX_VENTAS]", max_client["Cliente"])
                        response_text = response_text.replace("[MONTO_MAX_VENTAS]", f"{max_client['Monto Facturado']:,.0f}")
                        st.success(response_text)

                    elif calculation_type == "min_month_sales":
                        # Agrupar por mes y sumar ventas
                        df_monthly = df.set_index("Fecha").resample("M")["Monto Facturado"].sum().reset_index()
                        min_month = df_monthly.loc[df_monthly["Monto Facturado"].idxmin()]

                        response_text = response_text.replace("[MES_MIN_INGRESOS]", min_month["Fecha"].strftime("%B %Y"))
                        response_text = response_text.replace("[MONTO_MIN_INGRESOS]", f"{min_month['Monto Facturado']:,.0f}")
                        st.success(response_text)
                    
                    elif calculation_type == "sales_for_period":
                        year = calculation_params.get("year")
                        month = calculation_params.get("month")

                        if year and not month:
                            # Cálculo para un año específico
                            sales = df[df["Fecha"].dt.year == year]["Monto Facturado"].sum()
                            response_text = response_text.replace("[YEAR]", str(year))
                            response_text = response_text.replace("[CALCULATED_TOTAL_YEAR]", f"{sales:,.0f}")
                            st.success(response_text)
                        elif year and month:
                            # Cálculo para un mes y año específicos
                            df_month = df[(df["Fecha"].dt.year == year) & (df["Fecha"].dt.month == month)]
                            sales = df_month["Monto Facturado"].sum()
                            
                            month_name = datetime(year, month, 1).strftime("%B")
                            response_text = response_text.replace("[MONTH]", month_name)
                            response_text = response_text.replace("[YEAR]", str(year))
                            response_text = response_text.replace("[CALCULATED_SALES_MONTH_YEAR]", f"{sales:,.0f}")
                            st.success(response_text)
                        else:
                            st.error("No se pudo determinar el período para el cálculo.")

                    elif calculation_type == "project_remaining_year":
                        today = datetime.now()
                        target_year = calculation_params.get("target_year", today.year)
                        
                        df_monthly = df.set_index("Fecha").resample("M")["Monto Facturado"].sum().to_frame()
                        
                        if len(df_monthly) < 12:
                            st.warning("Se necesitan al menos 12 meses de datos para una proyección fiable. Realizando una proyección simple.")
                            avg_monthly_sales = df_monthly["Monto Facturado"].mean()
                            remaining_months = 12 - today.month
                            projected_sales = avg_monthly_sales * remaining_months
                            
                            st.info(f"Proyección simple para el resto de {target_year}: ${projected_sales:,.0f} (basado en un promedio mensual de ${avg_monthly_sales:,.0f}).")
                        else:
                            try:
                                # Descomposición de la serie de tiempo para capturar estacionalidad
                                decomp = seasonal_decompose(df_monthly, model='additive')
                                last_trend = decomp.trend.iloc[-1]
                                last_seasonal = decomp.seasonal.iloc[-1]
                                last_value = df_monthly["Monto Facturado"].iloc[-1]
                                remaining_months = 12 - today.month
                                
                                projections = []
                                for i in range(1, remaining_months + 1):
                                    # Proyectar el siguiente punto de la serie
                                    next_date = today + relativedelta(months=i)
                                    # La estacionalidad se repite en el ciclo
                                    seasonal_idx = next_date.month - 1
                                    seasonal_val = decomp.seasonal.iloc[seasonal_idx]
                                    
                                    # Simple proyección de tendencia + estacionalidad
                                    # Esto es una simplificación, un modelo de ML sería más preciso
                                    next_projection = last_value + (decomp.trend.diff().mean() * i) + seasonal_val
                                    projections.append(next_projection)

                                projected_sales = sum(projections)
                                response_text = response_text.replace("[TARGET_YEAR]", str(target_year))
                                response_text = response_text.replace("[ESTIMACION_RESTO_YEAR]", f"{projected_sales:,.0f}")
                                st.success(response_text)
                                st.info("Esta es una estimación basada en un modelo de series de tiempo y no es una garantía financiera.")
                            except Exception as e:
                                st.error(f"Ocurrió un error al realizar la proyección: {e}. Asegúrate de que tus datos de 'Fecha' y 'Monto Facturado' sean continuos y válidos.")
                    
                    elif calculation_type == "project_remaining_year_monthly":
                        today = datetime.now()
                        target_year = calculation_params.get("target_year", today.year)
                        
                        df_monthly = df.set_index("Fecha").resample("M")["Monto Facturado"].sum().to_frame()
                        
                        if len(df_monthly) < 12:
                            st.warning("Se necesitan al menos 12 meses de datos para una proyección fiable. Realizando una proyección simple.")
                            avg_monthly_sales = df_monthly["Monto Facturado"].mean()
                            remaining_months = 12 - today.month
                            
                            projected_data = {}
                            for i in range(1, remaining_months + 1):
                                next_month = today + relativedelta(months=i)
                                projected_data[next_month.strftime("%Y-%m")] = avg_monthly_sales
                            
                            st.subheader("Proyección Mensual Simple:")
                            st.dataframe(pd.DataFrame(projected_data.items(), columns=["Mes", "Ventas Estimadas"]).set_index("Mes"), use_container_width=True)
                            st.info("Esta proyección simple utiliza el promedio mensual de ventas. Para una mayor precisión, se necesitan más datos históricos.")

                        else:
                            try:
                                decomp = seasonal_decompose(df_monthly, model='additive')
                                last_value = df_monthly["Monto Facturado"].iloc[-1]
                                remaining_months = 12 - today.month
                                
                                projections = []
                                next_date_list = []
                                for i in range(1, remaining_months + 1):
                                    next_date = today + relativedelta(months=i)
                                    seasonal_idx = next_date.month - 1
                                    seasonal_val = decomp.seasonal.iloc[seasonal_idx]
                                    
                                    next_projection = last_value + (decomp.trend.diff().mean() * i) + seasonal_val
                                    projections.append(next_projection)
                                    next_date_list.append(next_date.strftime("%Y-%m"))
                                    
                                projected_df = pd.DataFrame({
                                    "Mes": next_date_list,
                                    "Ventas Estimadas": projections
                                }).set_index("Mes")

                                st.subheader("Proyección Mensual Detallada:")
                                st.dataframe(projected_df, use_container_width=True)
                                st.info("Esta es una estimación basada en un modelo de series de tiempo y no es una garantía financiera.")

                            except Exception as e:
                                st.error(f"Ocurrió un error al realizar la proyección: {e}. Asegúrate de que tus datos de 'Fecha' y 'Monto Facturado' sean continuos y válidos.")

                    elif calculation_type == "percentage_of_total_sales_by_category":
                        category_column = calculation_params.get("category_column")
                        category_value = calculation_params.get("category_value")
                        
                        if category_column and category_value and category_column in df.columns:
                            try:
                                total_sales = df["Monto Facturado"].sum()
                                sales_by_category = df[df[category_column].astype(str).str.lower() == category_value.lower()]["Monto Facturado"].sum()
                                
                                if total_sales > 0:
                                    percentage = (sales_by_category / total_sales) * 100
                                    response_text = response_text.replace("[PERCENTAJE]", f"{percentage:,.2f}")
                                    st.success(response_text)
                                else:
                                    st.warning(f"No se encontraron ventas para la categoría '{category_value}' o el total de ventas es cero.")
                            except KeyError:
                                st.error(f"No se encontró la columna 'Monto Facturado' o '{category_column}' en la hoja.")
                            except Exception as e:
                                st.error(f"Ocurrió un error al calcular el porcentaje: {e}")
                        else:
                            st.warning("No se pudieron extraer los parámetros necesarios para este cálculo.")

                    elif calculation_type == "recommendations":
                         # --- SEGUNDA LLAMADA A GEMINI PARA GENERAR RECOMENDACIONES ---
                        prompt_recommendations = f"""
                        Basado en la siguiente pregunta y el resumen de los datos disponibles, genera una respuesta útil y recomendaciones estratégicas en español.

                        **Pregunta del usuario:**
                        {pregunta}

                        **Resumen de la hoja de cálculo activa ('{st.session_state.selected_sheet}'):**
                        {df_summary_str}

                        **Instrucciones para la respuesta:**
                        - Ofrece recomendaciones accionables para mejorar los resultados financieros.
                        - Utiliza los datos del resumen para respaldar tus recomendaciones (ej: "Dado que el cliente con más ventas es...", "Dado que los meses con menor venta son...").
                        - Responde de forma amigable, directa y profesional.
                        - No inventes datos que no estén en el resumen.
                        - Concluye con una advertencia de que son recomendaciones generales y deben ser validadas por un profesional.

                        **Respuesta:**
                        """
                        
                        recommendations_payload = {
                            "contents": [
                                {
                                    "role": "user",
                                    "parts": [{"text": prompt_recommendations}]
                                }
                            ]
                        }

                        with st.spinner("Generando recomendaciones..."):
                            try:
                                response_recommendations = requests.post(api_url, headers={"Content-Type": "application/json"}, json=recommendations_payload, timeout=30)
                                response_recommendations.raise_for_status()
                                final_response = response_recommendations.json()["candidates"][0]["content"]["parts"][0]["text"]
                                st.markdown(final_response)
                            except requests.exceptions.RequestException as e:
                                st.error(f"❌ Error de conexión con la API de Gemini al generar recomendaciones: {e}")
                                st.stop()
                            except (KeyError, IndexError, json.JSONDecodeError) as e:
                                st.error(f"❌ Error al procesar la respuesta de la API de Gemini: {e}")
                                st.write("Respuesta de la API:", response_recommendations.text)
                                st.stop()
                    
                    else:
                        st.markdown(response_text)


    # --- Historial de Preguntas Recientes (en la barra lateral) ---
    st.sidebar.title("💬 Historial de Consultas")
    if st.session_state.question_history:
        for i, q in enumerate(reversed(st.session_state.question_history)):
            st.sidebar.write(f"{len(st.session_state.question_history)-i}. {q}")
