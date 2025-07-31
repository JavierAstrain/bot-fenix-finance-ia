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

# Inicializar el estado de la sesión para el login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "question_history" not in st.session_state:
    st.session_state.question_history = []


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
if not st.session_state.logged_in:
    show_login_form()
else:
    # --- AGREGAR LOGO DE LA EMPRESA Y TÍTULO ---
    col_title, col_logo = st.columns([0.7, 0.3]) # 70% para título, 30% para logo

    with col_title:
        st.title("🤖 Bot Fénix Finance IA")

    with col_logo:
        try:
            # En un entorno de producción, asegúrate de que esta imagen esté accesible.
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


    # --- CARGA DATOS DESDE GOOGLE SHEET (NUEVA URL) ---
    # Actualizamos la URL a la nueva planilla proporcionada por el usuario.
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1SaXuzhY_sJ9Tk9MOLDLAI4OVdsNbCP-X4L8cP15yTqo/edit?gid=0#gid=0"
    
    try:
        # Abrimos la nueva planilla
        spreadsheet = client.open_by_url(SHEET_URL)
        
        # Obtenemos todas las hojas
        worksheets = spreadsheet.worksheets()
        
        # Creamos una lista para almacenar los DataFrames de cada hoja
        dfs = []
        
        # Iteramos sobre cada hoja para leer los datos
        for sheet in worksheets:
            st.info(f"Cargando datos de la hoja: **{sheet.title}**")
            data = sheet.get_all_values()
            
            # Verificamos que la hoja no esté vacía
            if data and len(data) > 1:
                df_temp = pd.DataFrame(data[1:], columns=data[0])
                # Agregamos la columna de origen de la hoja para referencia
                df_temp['Origen_Hoja'] = sheet.title
                dfs.append(df_temp)
            else:
                st.warning(f"La hoja '{sheet.title}' está vacía y será ignorada.")
        
        # Concatenamos todos los DataFrames
        if dfs:
            df = pd.concat(dfs, ignore_index=True)
        else:
            st.error("❌ No se encontraron datos válidos en ninguna de las hojas de la planilla.")
            st.stop()
            
        # --- Limpiar nombres de columnas (eliminar espacios en blanco alrededor) ---
        df.columns = df.columns.str.strip()

        # --- Verificación de columnas esenciales al inicio (con los nuevos nombres) ---
        # He actualizado esta lista con nombres de columnas probables,
        # pero DEBES verificar y ajustar estos nombres si no son exactos.
        required_columns = ["Fecha", "Monto", "Cliente", "Tipo_Cliente"]
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            st.error(f"❌ Faltan columnas esenciales en tu hoja de cálculo: {', '.join(missing_columns)}. Por favor, asegúrate de que tu hoja contenga estas columnas con los nombres **exactos**.")
            st.stop()

        # Convertir tipos de datos
        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
        
        # --- Limpieza y conversión más robusta para columnas numéricas ---
        numeric_cols = ["Monto", "Descuento", "Costos_Financieros"] # Nombres de columnas actualizados
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].astype(str)
                df[col] = df[col].str.replace('[$,.]', '', regex=True)
                df[col] = df[col].str.replace(',', '.', regex=False)
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Eliminar filas con valores NaN en columnas críticas para el análisis
        df.dropna(subset=["Fecha", "Monto"], inplace=True)

        # --- Verificar si el DataFrame está vacío después de la limpieza ---
        if df.empty:
            st.error("⚠️ Después de cargar y limpiar los datos, no se encontraron filas válidas con 'Fecha' y 'Monto Facturado'. Por favor, revisa tu hoja de cálculo.")
            st.stop() # Detiene la ejecución si no hay datos válidos

        # --- Mostrar vista previa de los datos después de la carga y limpieza ---
        st.subheader("📊 Vista previa de los datos:")
        st.dataframe(df.head(10))

        # --- Generar información dinámica de columnas para el prompt de Gemini ---
        available_columns_info = []
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
        
        df_summary_str = "\n".join(df_summary_parts)


        # --- Sección de "Qué puedes preguntar" ---
        with st.expander("💡 ¿Qué puedes preguntar y cuáles son los alcances de este bot?"):
            st.write("""
            Este bot de Fénix Finance IA está diseñado para ayudarte a analizar tus datos financieros. Puedes:

            * **Consultar Datos Específicos y Generar Tablas:**
                * Ej: "¿Cuál fue el Monto total en el mes de marzo de 2025?"
                * Ej: "**Muéstrame una tabla** con los Montos por cada Tipo Cliente."
                * Ej: "**Lista** las 5 transacciones con mayor Monto."
                * Ej: "Dime el total de ventas para el Tipo Cliente 'Particular' en 2024."

            * **Realizar Cálculos Financieros:**
                * Ej: "¿Cuál es la variación porcentual en cuanto a costos financieros entre el año 2023 y 2024?"
                * Ej: "Calcula el promedio de 'Monto' por 'Sucursal'."
                * Ej: "Cuál es el total de 'Costos_Financieros' para el año 2024?"
                * **Ej: "Qué porcentaje de venta corresponde a particular?"**
                * **Ej: "Dame el porcentaje de ventas de pesado."**

            * **Generar Gráficos Interactivos:**
                * **Evolución:** "Hazme un gráfico de línea con la evolución de Monto en 2023."
                * **Comparación:** "Muestra un gráfico de barras del Monto por mes."
                * **Segmentación:** "Crea un gráfico de evolución de ventas de 2025 separado por Tipo Cliente."
                * **Rangos de Fecha:** "Gráfico de Monto entre 2024-01-15 y 2024-04-30."
                * **Tipos de Gráfico:** Línea, barras, pastel, dispersión.

            * **Realizar Análisis y Obtener Perspectivas:**
                * Ej: "¿Qué tendencias observas en mis Montos?"
                * Ej: "¿Hubo alguna anomalía en las ventas del último trimestre?"
                * Ej: "Dame un análisis de los datos de 2024."
                * Ej: "¿Cuál es el cliente que genera mayor cantidad de ventas?"
                * **Ej: "¿Cómo puedo mejorar las ventas de lo que queda del 2025?"**

            * **Hacer Estimaciones y Proyecciones (con cautela y estacionalidad):**
                * Ej: "¿Podrías proyectar el Monto para el próximo mes basándote en los datos históricos?"
                * **Ej: "Hazme una estimación de la venta para lo que queda de 2025 por mes, considerando estacionalidades."**
                * **Alcance:** Las proyecciones se basan en los datos históricos proporcionados y utilizan modelos de series de tiempo para intentar capturar estacionalidades. **No son consejos financieros garantizados y su precisión depende de la calidad y extensión de tus datos históricos.**

            * **Recibir Recomendaciones Estratégicas:**
                * Ej: "¿Qué recomendaciones me darías para mejorar mi Monto?"
                * **Alcance:** Las recomendaciones se derivan del análisis de tus datos y buscan ofrecer ideas accionables. **Siempre consulta con un profesional financiero antes de tomar decisiones importantes.**

            **Importante:**
            * El bot solo puede analizar la información presente en tu hoja de cálculo.
            * Asegúrate de que los nombres de las columnas que mencionas en tus preguntas (ej. 'Fecha', 'Monto', 'Tipo Cliente') coincidan **exactamente** con los de tu hoja.
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
                                -   `y_axis`: String. Nombre de la columna para el eje Y (ej: 'Monto'). Vacío si no es gráfico.
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
                                -   "evolución de ventas del año 2025": {{"is_chart_request": true, "chart_type": "line", "x_axis": "Fecha", "y_axis": "Monto", "filter_column": "Fecha", "filter_value": "2025", "color_column": "", "start_date": "", "end_date": "", "additional_filters": [], "summary_response": "Aquí tienes la evolución de ventas para el año 2025:", "aggregation_period": "month", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                                -   "ventas por mes": {{"is_chart_request": true, "chart_type": "bar", "x_axis": "Fecha", "y_axis": "Monto", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": "", "additional_filters": [], "summary_response": "Aquí tienes un gráfico de barras de las ventas por mes:", "aggregation_period": "month", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                                -   "gráfico de barras de montos por Tipo Cliente": {{"is_chart_request": true, "chart_type": "bar", "x_axis": "Tipo_Cliente", "y_axis": "Monto", "filter_column": "", "filter_value": "", "color_column": "Tipo_Cliente", "start_date": "", "end_date": "", "additional_filters": [], "summary_response": "Aquí tienes un gráfico de barras de los montos por Tipo Cliente:", "aggregation_period": "none", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                                -   "creame un grafico con la evolucion de ventas de 2025 separado por particular y seguro": {{"is_chart_request": true, "chart_type": "line", "x_axis": "Fecha", "y_axis": "Monto", "filter_column": "Fecha", "filter_value": "2025", "color_column": "Tipo_Cliente", "start_date": "", "end_date": "", "additional_filters": [], "summary_response": "Aquí tienes la evolución de ventas de 2025, separada por particular y seguro:", "aggregation_period": "month", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                                -   "ventas entre 2024-03-01 y 2024-06-30": {{"is_chart_request": true, "chart_type": "line", "x_axis": "Fecha", "y_axis": "Monto", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "2024-03-01", "end_date": "2024-06-30", "additional_filters": [], "summary_response": "Aquí tienes la evolución de ventas entre marzo y junio de 2024:", "aggregation_period": "month", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                                -   "ventas de particular en el primer trimestre de 2025": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "Fecha", "filter_value": "2025", "color_column": "", "start_date": "2025-01-01", "end_date": "2025-03-31", "additional_filters": [{{"column": "Tipo_Cliente", "value": "particular"}}], "summary_response": "Aquí tienes las ventas de clientes particulares en el primer trimestre de 2025:", "aggregation_period": "month", "table_columns": [], "calculation_type": "sales_for_period", "calculation_params": {{"year": 2025, "month": 1}}}}
                                -   "analisis de mis ingresos": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "", "aggregation_period": "none", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                                -   "qué cliente vendía más": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Basado en tus datos, el cliente que generó la mayor cantidad de ventas es [NOMBRE_CLIENTE_MAX_VENTAS] con un total de $[MONTO_MAX_VENTAS].", "aggregation_period": "none", "table_columns": [], "calculation_type": "max_client_sales", "calculation_params": {{}}}}
                                -   "dame el total de ventas": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "El monto total facturado en todos los datos es de $[TOTAL_MONTO].", "aggregation_period": "none", "table_columns": [], "calculation_type": "total_sales", "calculation_params": {{}}}}
                                -   "cuál fue el mes con menos ingresos": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "El mes con menos ingresos fue [MES_MIN_INGRESOS] con un total de $[MONTO_MIN_INGRESOS].", "aggregation_period": "none", "table_columns": [], "calculation_type": "min_month_sales", "calculation_params": {{}}}}
                                -   "hazme una estimacion de cual seria la venta para lo que queda de 2025": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "Fecha", "filter_value": "2025", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Aquí tienes una estimación de las ventas para lo que queda de [TARGET_YEAR]: $[ESTIMACION_RESTO_YEAR]. Ten en cuenta que esta es una proyección basada en datos históricos y no una garantía financiera.", "aggregation_period": "none", "table_columns": [], "calculation_type": "project_remaining_year", "calculation_params": {{"target_year": 2025}}}}
                                -   "muéstrame una tabla de los montos por cliente": {{"is_chart_request": true, "chart_type": "table", "x_axis": "Cliente", "y_axis": "Monto", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Aquí tienes una tabla con los montos por Cliente:", "aggregation_period": "none", "table_columns": ["Cliente", "Monto"], "calculation_type": "none", "calculation_params": {{}}}}
                                -   "lista las ventas de cada tipo de cliente": {{"is_chart_request": true, "chart_type": "table", "x_axis": "Tipo_Cliente", "y_axis": "Monto", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Aquí tienes una tabla con las ventas por Tipo Cliente:", "aggregation_period": "none", "table_columns": ["Tipo_Cliente", "Monto"], "calculation_type": "none", "calculation_params": {{}}}}
                                -   "ventas mensuales de 2023": {{"is_chart_request": true, "chart_type": "line", "x_axis": "Fecha", "y_axis": "Monto", "filter_column": "Fecha", "filter_value": "2023", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Aquí tienes las ventas mensuales de 2023:", "aggregation_period": "month", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                                -   "ventas por año": {{"is_chart_request": true, "chart_type": "bar", "x_axis": "Fecha", "y_axis": "Monto", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Aquí tienes las ventas agrupadas por año:", "aggregation_period": "year", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                                -   "total facturado en 2024": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "Fecha", "filter_value": "2024", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "El monto total facturado en [YEAR] fue de $[CALCULATED_TOTAL_YEAR].", "aggregation_period": "year", "table_columns": [], "calculation_type": "sales_for_period", "calculation_params": {{"year": 2024}}}}
                                -   "ventas de enero 2025": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "Fecha", "filter_value": "Enero", "color_column": "", "start_date": "2025-01-01", "end_date": "2025-01-31", "additional_filters": [], "summary_response": "Las ventas de [MONTH] de [YEAR] fueron de $[CALCULATED_SALES_MONTH_YEAR].", "aggregation_period": "month", "table_columns": [], "calculation_type": "sales_for_period", "calculation_params": {{"year": 2025, "month": 1}}}}
                                -   "cómo puedo mejorar las ventas de lo que queda del 2025": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "", "aggregation_period": "none", "table_columns": [], "calculation_type": "recommendations", "calculation_params": {{}}}}

                                **Instrucciones:** Mapea la siguiente pregunta del usuario al formato JSON anterior. Devuelve solo el JSON.
                                Pregunta del usuario: {pregunta}
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
                            "is_chart_request": {"type": "BOOLEAN"},
                            "chart_type": {"type": "STRING"},
                            "x_axis": {"type": "STRING"},
                            "y_axis": {"type": "STRING"},
                            "color_column": {"type": "STRING"},
                            "filter_column": {"type": "STRING"},
                            "filter_value": {"type": "STRING"},
                            "start_date": {"type": "STRING"},
                            "end_date": {"type": "STRING"},
                            "additional_filters": {
                                "type": "ARRAY",
                                "items": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "column": {"type": "STRING"},
                                        "value": {"type": "STRING"}
                                    }
                                }
                            },
                            "summary_response": {"type": "STRING"},
                            "aggregation_period": {"type": "STRING"},
                            "table_columns": {
                                "type": "ARRAY",
                                "items": {"type": "STRING"}
                            },
                            "calculation_type": {"type": "STRING"},
                            "calculation_params": {"type": "OBJECT"}
                        }
                    }
                }
            }

            try:
                # Se realiza la llamada a la API de Gemini para la detección de intención
                response = requests.post(api_url, headers={"Content-Type": "application/json"}, json=chart_detection_payload, timeout=30)
                response.raise_for_status() # Lanza una excepción para errores HTTP
                response_json = response.json()
                
                # Accedemos al contenido JSON
                parsed_response = json.loads(response_json["candidates"][0]["content"]["parts"][0]["text"])

                is_chart_request = parsed_response.get("is_chart_request")
                chart_type = parsed_response.get("chart_type")
                x_axis = parsed_response.get("x_axis")
                y_axis = parsed_response.get("y_axis")
                color_column = parsed_response.get("color_column")
                start_date_str = parsed_response.get("start_date")
                end_date_str = parsed_response.get("end_date")
                additional_filters = parsed_response.get("additional_filters", [])
                summary_response = parsed_response.get("summary_response")
                aggregation_period = parsed_response.get("aggregation_period")
                table_columns = parsed_response.get("table_columns")
                calculation_type = parsed_response.get("calculation_type")
                calculation_params = parsed_response.get("calculation_params", {})
                
                # --- Procesamiento de la respuesta ---
                st.write("---")
                
                # Crear un DataFrame de trabajo para el análisis
                df_filtered = df.copy()

                # --- Aplicar filtros adicionales ---
                for filter_obj in additional_filters:
                    col = filter_obj.get("column")
                    val = filter_obj.get("value")
                    if col and val and col in df_filtered.columns:
                        df_filtered = df_filtered[df_filtered[col].astype(str).str.contains(val, case=False, na=False)]
                
                # --- Aplicar filtro de rango de fechas ---
                if start_date_str and end_date_str:
                    try:
                        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
                        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
                        df_filtered = df_filtered[(df_filtered["Fecha"] >= start_date) & (df_filtered["Fecha"] <= end_date)]
                    except ValueError:
                        st.warning("El formato de fecha no es válido. Usa YYYY-MM-DD.")
                
                # --- Lógica para cálculos directos y análisis ---
                if not is_chart_request:
                    
                    if calculation_type == "total_sales":
                        total_sales = df_filtered[y_axis].sum()
                        summary_response = summary_response.replace("[TOTAL_MONTO]", f"{total_sales:,.2f}")
                        st.success(summary_response)
                        
                    elif calculation_type == "max_client_sales":
                        if "Cliente" in df_filtered.columns and "Monto" in df_filtered.columns:
                            sales_by_client = df_filtered.groupby("Cliente")["Monto"].sum().sort_values(ascending=False)
                            max_client = sales_by_client.index[0]
                            max_sales = sales_by_client.iloc[0]
                            summary_response = summary_response.replace("[NOMBRE_CLIENTE_MAX_VENTAS]", max_client)
                            summary_response = summary_response.replace("[MONTO_MAX_VENTAS]", f"{max_sales:,.2f}")
                            st.success(summary_response)
                        else:
                            st.error("❌ Las columnas 'Cliente' o 'Monto' no están disponibles para este cálculo.")

                    elif calculation_type == "min_month_sales":
                        if "Fecha" in df_filtered.columns and "Monto" in df_filtered.columns:
                            df_monthly = df_filtered.resample('M', on='Fecha')["Monto"].sum()
                            min_month = df_monthly.idxmin().strftime('%B de %Y')
                            min_sales = df_monthly.min()
                            summary_response = summary_response.replace("[MES_MIN_INGRESOS]", min_month)
                            summary_response = summary_response.replace("[MONTO_MIN_INGRESOS]", f"{min_sales:,.2f}")
                            st.success(summary_response)
                        else:
                            st.error("❌ Las columnas 'Fecha' o 'Monto' no están disponibles para este cálculo.")

                    elif calculation_type == "sales_for_period":
                        # Se puede mejorar para manejar meses y años dinámicamente
                        if "year" in calculation_params:
                            year = calculation_params.get("year")
                            total_sales = df_filtered[df_filtered["Fecha"].dt.year == year]["Monto"].sum()
                            summary_response = summary_response.replace("[YEAR]", str(year))
                            summary_response = summary_response.replace("[CALCULATED_TOTAL_YEAR]", f"{total_sales:,.2f}")
                            st.success(summary_response)
                        elif "month" in calculation_params and "year" in calculation_params:
                             year = calculation_params.get("year")
                             month = calculation_params.get("month")
                             sales = df_filtered[(df_filtered['Fecha'].dt.year == year) & (df_filtered['Fecha'].dt.month == month)]['Monto'].sum()
                             month_name = datetime.strptime(str(month), "%m").strftime("%B").capitalize()
                             summary_response = summary_response.replace("[MONTH]", month_name)
                             summary_response = summary_response.replace("[YEAR]", str(year))
                             summary_response = summary_response.replace("[CALCULATED_SALES_MONTH_YEAR]", f"{sales:,.2f}")
                             st.success(summary_response)
                        else:
                            st.error("No se pudo calcular las ventas para el período especificado.")
                            
                    elif calculation_type == "percentage_of_total_sales_by_category":
                        total_sales = df_filtered["Monto"].sum()
                        if total_sales > 0 and color_column and color_column in df_filtered.columns:
                            sales_by_category = df_filtered.groupby(color_column)["Monto"].sum()
                            percentage = (sales_by_category / total_sales) * 100
                            
                            st.subheader(f"Porcentaje de Ventas por '{color_column}'")
                            st.dataframe(percentage.reset_index(name='Porcentaje').sort_values('Porcentaje', ascending=False))
                            
                            st.success(f"El porcentaje de ventas para cada categoría en '{color_column}' es el siguiente:")

                    elif calculation_type == "project_remaining_year":
                        
                        # Lógica para la proyección
                        target_year = calculation_params.get("target_year")
                        if not target_year:
                             st.error("No se especificó el año para la proyección.")
                             continue
                        
                        df_time_series = df_filtered.set_index("Fecha")["Monto"].resample("MS").sum() # Resample a inicio de mes
                        
                        # Se requiere un mínimo de 2 años de datos para una descomposición de series de tiempo
                        if len(df_time_series) < 24:
                            st.warning("⚠️ No hay suficientes datos (se necesitan al menos 24 meses) para una proyección estacional confiable. Realizando una proyección simple con el promedio.")
                            
                            # Proyección simple: promedio de ventas mensuales
                            monthly_avg = df_time_series.mean()
                            current_month = datetime.now().month
                            months_left = 12 - current_month
                            projection = monthly_avg * months_left
                            
                            summary_response = summary_response.replace("[TARGET_YEAR]", str(target_year))
                            summary_response = summary_response.replace("[ESTIMACION_RESTO_YEAR]", f"{projection:,.2f}")
                            st.success(summary_response)
                            st.write("---")
                            st.warning("Esta es una estimación simple. Para mayor precisión, se recomienda tener más datos históricos.")
                            
                        else:
                            # Descomposición de series de tiempo para obtener la estacionalidad
                            decomposition = seasonal_decompose(df_time_series, model='additive', period=12) # Se asume una estacionalidad de 12 meses
                            seasonal_component = decomposition.seasonal
                            
                            # Promedio de ventas históricas (sin estacionalidad)
                            trend_component = decomposition.trend.dropna()
                            avg_trend = trend_component.mean()
                            
                            # Proyectar ventas para el resto del año
                            projection_data = []
                            today = datetime.now()
                            current_year = today.year
                            
                            for month_offset in range(12 - today.month + 1):
                                # Calcular la fecha del mes proyectado
                                target_date = today + relativedelta(months=month_offset)
                                
                                # Obtener el valor de estacionalidad para el mes
                                seasonal_value = seasonal_component.iloc[(target_date.month - 1) % 12] # Mapea el mes a la componente estacional
                                
                                # Calcular la proyección
                                projected_value = avg_trend + seasonal_value
                                projection_data.append({'Fecha': target_date, 'Monto Proyectado': projected_value})

                            df_projection = pd.DataFrame(projection_data)
                            total_projection = df_projection['Monto Proyectado'].sum()
                            
                            summary_response = summary_response.replace("[TARGET_YEAR]", str(target_year))
                            summary_response = summary_response.replace("[ESTIMACION_RESTO_YEAR]", f"{total_projection:,.2f}")
                            st.success(summary_response)
                            st.write("---")
                            st.subheader("Estimación de Ventas para lo que queda del 2025 (por mes):")
                            st.dataframe(df_projection)

                            # Gráfico de la proyección
                            fig = px.line(df_projection, x='Fecha', y='Monto Proyectado', title=f"Proyección de Montos para {target_year}")
                            fig.update_layout(xaxis_title="Fecha", yaxis_title="Monto Proyectado", hovermode="x unified")
                            st.plotly_chart(fig, use_container_width=True)

                    elif calculation_type == "recommendations":
                        # Lógica para generar recomendaciones
                        
                        # Llamada a Gemini para generar recomendaciones basadas en el resumen de datos
                        recommendations_prompt = f"""
                        Eres un experto consultor financiero. Basado en el siguiente resumen de datos, proporciona 3-5 recomendaciones estratégicas y accionables para la empresa Fenix Finance IA. Las recomendaciones deben ser directas, prácticas y basarse en las tendencias o puntos clave que identifiques en los datos. No pidas más información, usa solo la que tienes.
                        
                        Resumen de los datos:
                        {df_summary_str}
                        
                        Pregunta del usuario: "{pregunta}"
                        
                        Tu respuesta debe ser en formato de lista amigable, por ejemplo:
                        "Basado en tus datos, aquí tienes algunas recomendaciones para mejorar tus ventas:
                        - **Recomendación 1:** [Detalle]
                        - **Recomendación 2:** [Detalle]
                        - **Recomendación 3:** [Detalle]"
                        """
                        
                        recommendations_payload = {
                            "contents": [
                                {
                                    "role": "user",
                                    "parts": [{"text": recommendations_prompt}]
                                }
                            ]
                        }
                        
                        with st.spinner("Analizando tus datos para generar recomendaciones..."):
                            response_reco = requests.post(api_url, headers={"Content-Type": "application/json"}, json=recommendations_payload, timeout=60)
                            response_reco.raise_for_status()
                            
                            recommendations_text = response_reco.json()["candidates"][0]["content"]["parts"][0]["text"]
                            st.markdown(recommendations_text)
                            st.info("⚠️ Estas recomendaciones son generadas por IA. Consulta siempre con un profesional financiero antes de tomar decisiones importantes.")

                    else:
                        # Si no es un cálculo específico, se envía un prompt final para una respuesta textual
                        final_prompt = f"""
                        Eres un asesor financiero experto. Basado en el siguiente resumen de datos de la empresa Fenix Finance IA y en la pregunta del usuario, proporciona una respuesta detallada, precisa y profesional. Puedes realizar cálculos simples como sumas, promedios, máximos y mínimos si es necesario.
                        
                        Resumen de los datos:
                        {df_summary_str}
                        
                        Historial de preguntas: {st.session_state.question_history}
                        
                        Pregunta del usuario: "{pregunta}"
                        
                        Responde de forma clara y concisa, yendo directamente al punto. No incluyas información adicional que no haya sido solicitada. Si necesitas realizar un cálculo simple, hazlo y muestra el resultado directamente.
                        """
                        
                        final_payload = {
                            "contents": [
                                {
                                    "role": "user",
                                    "parts": [{"text": final_prompt}]
                                }
                            ]
                        }
                        
                        with st.spinner("Analizando tu pregunta..."):
                            response_final = requests.post(api_url, headers={"Content-Type": "application/json"}, json=final_payload, timeout=60)
                            response_final.raise_for_status()
                            
                            final_text = response_final.json()["candidates"][0]["content"]["parts"][0]["text"]
                            st.markdown(final_text)

                # --- Lógica para gráficos y tablas ---
                else:
                    if summary_response:
                        st.subheader("Respuesta del bot:")
                        st.markdown(summary_response)

                    if chart_type == "table":
                        # Agregamos si la tabla tiene una columna para agregar
                        if x_axis and y_axis:
                            df_table = df_filtered.groupby(x_axis)[y_axis].sum().reset_index()
                            st.dataframe(df_table)
                        else:
                            # Se muestra la tabla sin agrupaciones
                            st.dataframe(df_filtered[table_columns])

                    else: # Gráficos
                        if x_axis in df_filtered.columns and y_axis in df_filtered.columns:
                            
                            # Preparar datos para el gráfico
                            if aggregation_period == "month":
                                df_chart = df_filtered.copy()
                                df_chart['Año-Mes'] = df_chart['Fecha'].dt.to_period('M').astype(str)
                                # Agrupar y sumar los valores
                                df_chart = df_chart.groupby(['Año-Mes', color_column if color_column else 'Año-Mes'])['Monto'].sum().reset_index()
                                df_chart['Fecha_Orden'] = pd.to_datetime(df_chart['Año-Mes'])
                                df_chart = df_chart.sort_values('Fecha_Orden')
                                
                                # Si no hay columna de color, usamos la columna agregada para el color.
                                if not color_column:
                                    color_column_final = 'Año-Mes'
                                else:
                                    color_column_final = color_column

                                # Crear el gráfico
                                fig = px.line(df_chart, x='Año-Mes', y='Monto', color=color_column_final,
                                            title=summary_response.replace("Aquí tienes ", "").replace(":", ""),
                                            labels={'Año-Mes': 'Fecha', 'Monto': 'Monto'})
                                fig.update_layout(xaxis_title="Fecha", yaxis_title="Monto", hovermode="x unified")
                                st.plotly_chart(fig, use_container_width=True)

                            elif aggregation_period == "year":
                                df_chart = df_filtered.copy()
                                df_chart['Año'] = df_chart['Fecha'].dt.year
                                df_chart = df_chart.groupby(['Año', color_column if color_column else 'Año'])['Monto'].sum().reset_index()
                                
                                if not color_column:
                                    color_column_final = 'Año'
                                else:
                                    color_column_final = color_column
                                
                                if chart_type == "bar":
                                    fig = px.bar(df_chart, x='Año', y='Monto', color=color_column_final,
                                                title=summary_response.replace("Aquí tienes ", "").replace(":", ""),
                                                labels={'Año': 'Año', 'Monto': 'Monto'})
                                    st.plotly_chart(fig, use_container_width=True)
                                else: # Por defecto, si el tipo no es barra, usamos linea para año
                                    fig = px.line(df_chart, x='Año', y='Monto', color=color_column_final,
                                                title=summary_response.replace("Aquí tienes ", "").replace(":", ""),
                                                labels={'Año': 'Año', 'Monto': 'Monto'})
                                    st.plotly_chart(fig, use_container_width=True)
                            
                            else: # Sin agregación de tiempo (por ejemplo, gráfico de barras por categoría)
                                # Agrupar datos para el gráfico de barras o pastel
                                df_grouped = df_filtered.groupby(x_axis)[y_axis].sum().reset_index()
                                
                                if chart_type == "bar":
                                    fig = px.bar(df_grouped, x=x_axis, y=y_axis,
                                                title=summary_response.replace("Aquí tienes ", "").replace(":", ""))
                                    st.plotly_chart(fig, use_container_width=True)
                                elif chart_type == "pie":
                                    fig = px.pie(df_grouped, values=y_axis, names=x_axis,
                                                title=summary_response.replace("Aquí tienes ", "").replace(":", ""))
                                    st.plotly_chart(fig, use_container_width=True)
                                elif chart_type == "line":
                                    fig = px.line(df_filtered, x=x_axis, y=y_axis, color=color_column,
                                                title=summary_response.replace("Aquí tienes ", "").replace(":", ""))
                                    fig.update_layout(xaxis_title=x_axis, yaxis_title=y_axis, hovermode="x unified")
                                    st.plotly_chart(fig, use_container_width=True)
                                else:
                                    st.warning("Tipo de gráfico no compatible o columnas no especificadas correctamente.")

                        else:
                            st.warning("No se pudo generar el gráfico. Las columnas especificadas no son válidas o no existen.")

            except requests.exceptions.RequestException as e:
                st.error(f"❌ Error al comunicarse con la API de Gemini: {e}")
            except json.JSONDecodeError:
                st.error("❌ La respuesta de la API de Gemini no es un JSON válido.")
            except Exception as e:
                st.error(f"❌ Ocurrió un error inesperado: {e}")
                st.write("Por favor, verifica tu pregunta y los datos en la planilla. Si el problema persiste, revisa el código en busca de errores.")

    except gspread.exceptions.APIError as e:
        st.error("❌ Error de la API de Google Sheets. Verifica que la URL sea correcta, que la cuenta de servicio tenga acceso y que la API de Google Sheets esté habilitada.")
        st.exception(e)
    except gspread.exceptions.SpreadsheetNotFound as e:
        st.error("❌ La planilla no se encontró en la URL proporcionada. Por favor, verifica el enlace.")
        st.exception(e)
    except Exception as e:
        st.error("❌ Ocurrió un error al cargar los datos desde Google Sheets.")
        st.exception(e)
