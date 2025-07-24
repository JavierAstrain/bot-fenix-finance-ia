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
USERNAME = "adm"
PASSWORD = "adm"

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


    # --- CARGA DATOS DESDE GOOGLE SHEET ---
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk/edit?gid=0#gid=0"

    try:
        sheet = client.open_by_url(SHEET_URL).sheet1
        data = sheet.get_all_values()
        df = pd.DataFrame(data[1:], columns=data[0])
        
        # --- Limpiar nombres de columnas (eliminar espacios en blanco alrededor) ---
        df.columns = df.columns.str.strip()

        # --- Verificación de columnas esenciales al inicio (con los nombres exactos del usuario) ---
        # Lista actualizada con los nombres de columnas proporcionados por el usuario
        required_columns = ["Fecha", "Cliente", "Tipo Cliente", "Tipo Vehículo", "Factura N°", 
                            "Monto Facturado", "Materiales y Pintura", "Costos Financieros", 
                            "Sucursal", "Ejecutivo", "Estado Pago", "Forma de Pago", 
                            "Descuento Aplicado (%)", "Observaciones"]
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            st.error(f"❌ Faltan columnas esenciales en tu hoja de cálculo: {', '.join(missing_columns)}. Por favor, asegúrate de que tu hoja contenga estas columnas con los nombres **exactos** (respetando mayúsculas, minúsculas y espacios).")
            st.stop()

        # Convertir tipos de datos
        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
        
        # --- Limpieza y conversión más robusta para 'Monto Facturado' ---
        if 'Monto Facturado' in df.columns:
            # Convertir a string primero para aplicar métodos de string
            df['Monto Facturado'] = df['Monto Facturado'].astype(str)
            # Eliminar símbolos de moneda y separadores de miles (puntos)
            df['Monto Facturado'] = df['Monto Facturado'].str.replace('[$,.]', '', regex=True)
            # Reemplazar separador decimal (coma) por punto
            df['Monto Facturado'] = df['Monto Facturado'].str.replace(',', '.', regex=False)
            # Convertir a numérico, 'coerce' convierte errores a NaN
            df['Monto Facturado'] = pd.to_numeric(df['Monto Facturado'], errors="coerce")
        
        # Convertir otras columnas numéricas relevantes a numérico (actualizado con los nombres del usuario)
        numeric_cols_other = ['Materiales y Pintura', 'Costos Financieros', 'Descuento Aplicado (%)']
        for col in numeric_cols_other:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Eliminar filas con valores NaN en columnas críticas para el análisis o gráficos
        df.dropna(subset=["Fecha", "Monto Facturado"], inplace=True)

        # --- Verificar si el DataFrame está vacío después de la limpieza ---
        if df.empty:
            st.error("⚠️ Después de cargar y limpiar los datos, no se encontraron filas válidas con 'Fecha' y 'Monto Facturado'. Por favor, revisa tu hoja de cálculo y asegúrate de que estas columnas contengan datos válidos y no estén vacías.")
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
                col_info += f" Estadísticas: Min={df[col].min():.2f}, Max={df[col].max():.2f}, Media={df[col].mean():.2f}, Suma={df[col].sum():.2f}"
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
                * Ej: "¿Cuál fue el Monto Facturado total en el mes de marzo de 2025?"
                * Ej: "**Muéstrame una tabla** con los Montos Facturados por cada Tipo Cliente."
                * Ej: "**Lista** las 5 transacciones con mayor Monto Facturado."
                * Ej: "Dime el total de ventas para el Tipo Cliente 'Particular' en 2024."

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
            * El bot solo puede analizar la información presente en tu hoja de cálculo.
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
                                -   `calculation_type`: String. Tipo de cálculo a realizar por Python. Enum: 'none', 'total_sales', 'max_client_sales', 'min_month_sales', 'sales_for_period', 'project_remaining_year', 'project_remaining_year_monthly', 'total_overdue_payments', 'recommendations'.
                                -   `calculation_params`: Objeto JSON. Parámetros para el cálculo (ej: {{"year": 2025}} para 'total_sales_for_year').

                                **Ejemplos de cómo mapear la intención (en formato JSON válido):**
                                -   "evolución de ventas del año 2025": {{"is_chart_request": true, "chart_type": "line", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "Fecha", "filter_value": "2025", "color_column": "", "start_date": "", "end_date": "", "additional_filters": [], "summary_response": "Aquí tienes la evolución de ventas para el año 2025:", "aggregation_period": "month", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                                -   "ventas por mes": {{"is_chart_request": true, "chart_type": "bar", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": "", "additional_filters": [], "summary_response": "Aquí tienes un gráfico de barras de las ventas por mes:", "aggregation_period": "month", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                                -   "gráfico de barras de montos facturados por Tipo Cliente": {{"is_chart_request": true, "chart_type": "bar", "x_axis": "Tipo Cliente", "y_axis": "Monto Facturado", "filter_column": "", "filter_value": "", "color_column": "Tipo Cliente", "start_date": "", "end_date": "", "additional_filters": [], "summary_response": "Aquí tienes un gráfico de barras de los montos facturados por Tipo Cliente:", "aggregation_period": "none", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                                -   "creame un grafico con la evolucion de ventas de 2025 separado por particular y seguro": {{"is_chart_request": true, "chart_type": "line", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "Fecha", "filter_value": "2025", "color_column": "Tipo Cliente", "start_date": "", "end_date": "", "additional_filters": [], "summary_response": "Aquí tienes la evolución de ventas de 2025, separada por particular y seguro:", "aggregation_period": "month", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                                -   "ventas entre 2024-03-01 y 2024-06-30": {{"is_chart_request": true, "chart_type": "line", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "2024-03-01", "end_date": "2024-06-30", "additional_filters": [], "summary_response": "Aquí tienes la evolución de ventas entre marzo y junio de 2024:", "aggregation_period": "month", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                                -   "ventas de particular en el primer trimestre de 2025": {{"is_chart_request": true, "chart_type": "line", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "Fecha", "filter_value": "2025", "color_column": "", "start_date": "2025-01-01", "end_date": "2025-03-31", "additional_filters": [{{"column": "Tipo Cliente", "value": "particular"}}], "summary_response": "Aquí tienes las ventas de clientes particulares en el primer trimestre de 2025:", "aggregation_period": "month", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                                -   "analisis de mis ingresos": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "", "aggregation_period": "none", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                                -   "qué cliente vendía más": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Basado en tus datos, el cliente que generó la mayor cantidad de ventas es [NOMBRE_CLIENTE_MAX_VENTAS] con un total de $[MONTO_MAX_VENTAS:.2f].", "aggregation_period": "none", "table_columns": [], "calculation_type": "max_client_sales", "calculation_params": {{}}}}
                                -   "dame el total de ventas": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "El monto total facturado en todos los datos es de $[TOTAL_MONTO_FACTURADO:.2f].", "aggregation_period": "none", "table_columns": [], "calculation_type": "total_sales", "calculation_params": {{}}}}
                                -   "cuál fue el mes con menos ingresos": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "El mes con menos ingresos fue [MES_MIN_INGRESOS] con un total de $[MONTO_MIN_INGRESOS:.2f].", "aggregation_period": "none", "table_columns": [], "calculation_type": "min_month_sales", "calculation_params": {{}}}}
                                -   "hazme una estimacion de cual seria la venta para lo que queda de 2025": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "Fecha", "filter_value": "2025", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Aquí tienes una estimación de las ventas para lo que queda de 2025: $[ESTIMACION_RESTO_2025:.2f]. Ten en cuenta que esta es una proyección basada en datos históricos y no una garantía financiera.", "aggregation_period": "none", "table_columns": [], "calculation_type": "project_remaining_year", "calculation_params": {{"target_year": 2025}}}}
                                -   "muéstrame una tabla de los montos facturados por cliente": {{"is_chart_request": true, "chart_type": "table", "x_axis": "Cliente", "y_axis": "Monto Facturado", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Aquí tienes una tabla con los montos facturados por Cliente:", "aggregation_period": "none", "table_columns": ["Cliente", "Monto Facturado"], "calculation_type": "none", "calculation_params": {{}}}}
                                -   "lista las ventas de cada tipo de cliente": {{"is_chart_request": true, "chart_type": "table", "x_axis": "Tipo Cliente", "y_axis": "Monto Facturado", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Aquí tienes una tabla con las ventas por Tipo Cliente:", "aggregation_period": "none", "table_columns": ["Tipo Cliente", "Monto Facturado"], "calculation_type": "none", "calculation_params": {{}}}}
                                -   "ventas mensuales de 2023": {{"is_chart_request": true, "chart_type": "line", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "Fecha", "filter_value": "2023", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Aquí tienes las ventas mensuales de 2023:", "aggregation_period": "month", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                                -   "ventas por año": {{"is_chart_request": true, "chart_type": "bar", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Aquí tienes las ventas agrupadas por año:", "aggregation_period": "year", "table_columns": [], "calculation_type": "none", "calculation_params": {{}}}}
                                -   "total facturado en 2024": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "Fecha", "filter_value": "2024", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "El monto total facturado en 2024 fue de $[CALCULATED_TOTAL_2024:.2f].", "aggregation_period": "year", "table_columns": [], "calculation_type": "sales_for_period", "calculation_params": {{"year": 2024}}}}
                                -   "ventas de enero 2025": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "Fecha", "filter_value": "Enero", "color_column": "", "start_date": "2025-01-01", "end_date": "2025-01-31", "additional_filters": [], "summary_response": "Las ventas de enero de 2025 fueron de $[CALCULATED_SALES_ENERO_2025:.2f].", "aggregation_period": "month", "table_columns": [], "calculation_type": "sales_for_period", "calculation_params": {{"year": 2025, "month": 1}}}}
                                -   "cómo puedo mejorar las ventas de lo que queda del 2025": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "", "aggregation_period": "none", "table_columns": [], "calculation_type": "recommendations", "calculation_params": {{}}}}
                                -   "me puedes hacer una estimacion de cual seria la venta para lo que queda de 2025 por mes, considerando estacionalidades": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "Fecha", "filter_value": "2025", "color_column": "", "start_date": "", "end_date": "", "additional_filters": [], "summary_response": "Aquí tienes una estimación de las ventas mensuales para lo que queda de 2025, considerando patrones históricos y estacionalidades: [ESTIMACION_MENSUAL_RESTO_2025]. Ten en cuenta que esta es una proyección basada en datos históricos y no una garantía financiera.", "aggregation_period": "month", "table_columns": [], "calculation_type": "project_remaining_year_monthly", "calculation_params": {{"target_year": 2025}}}}
                                -   "cuanta facturacion esta en estado de pago vencido": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "Estado Pago", "filter_value": "Vencido", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "El monto total facturado con estado de pago vencido es de $[TOTAL_MONTO_VENCIDO:.2f].", "aggregation_period": "none", "table_columns": [], "calculation_type": "total_overdue_payments", "calculation_params": {{}}}}
                                -   "puedes darme insights de mejora para los proximos meses": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "", "aggregation_period": "none", "table_columns": [], "calculation_type": "recommendations", "calculation_params": {{}}}}

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
                                "description": "Tipo de visualización (line, bar, pie, scatter, table). 'none' if not a visualization or unclear type."
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
                                "description": "Nombre de la columna para colorear/agrupar (ej: 'Tipo Cliente'). Vacío si no se pide segmentación o la columna no existe."
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
                            "aggregation_period": {
                                "type": "STRING",
                                "enum": ["day", "month", "year", "none"],
                                "description": "Período de agregación para datos de tiempo (day, month, year) o 'none' if not applicable."
                            },
                            "table_columns": {
                                "type": "ARRAY",
                                "items": {"type": "STRING"},
                                "description": "Lista de nombres de columnas a mostrar en una tabla. Solo aplica si chart_type es 'table'."
                            },
                            "calculation_type": {
                                "type": "STRING",
                                "enum": ["none", "total_sales", "max_client_sales", "min_month_sales", "sales_for_period", "project_remaining_year", "project_remaining_year_monthly", "total_overdue_payments", "recommendations"],
                                "description": "Tipo de cálculo que Python debe realizar para la respuesta textual."
                            },
                            "calculation_params": {
                                "type": "OBJECT",
                                "description": "Parámetros adicionales necesarios para el cálculo (ej: {'year': 2025, 'month': 1}).",
                                "properties": {
                                    "year": {"type": "INTEGER", "description": "Año para el cálculo."},
                                    "month": {"type": "INTEGER", "description": "Mes para el cálculo."},
                                    "target_year": {"type": "INTEGER", "description": "Año objetivo para proyecciones."},
                                    "forecast_months": {"type": "INTEGER", "description": "Número de meses a pronosticar."}
                                }
                            }
                        },
                        "required": ["is_chart_request", "chart_type", "x_axis", "y_axis", "color_column", 
                                     "filter_column", "filter_value", "start_date", "end_date", 
                                     "additional_filters", "summary_response", "aggregation_period", 
                                     "table_columns", "calculation_type", "calculation_params"]
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
                            else:
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
                            aggregation_period = chart_data.get("aggregation_period", "none")
                            table_columns = chart_data.get("table_columns", [])

                            # Asegurarse de que color_col sea None si es una cadena vacía
                            if color_col == "":
                                color_col = None

                            # Validar que las columnas existan en el DataFrame antes de usarlas
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
                                color_col = None

                            # --- Lógica de Agregación y Visualización ---
                            fig = None
                            if chart_data["chart_type"] in ["line", "bar"]:
                                group_cols = []
                                x_col_for_plot = x_col

                                if x_col == "Fecha" and aggregation_period != "none":
                                    if aggregation_period == "month":
                                        filtered_df['Fecha_Agrupada'] = filtered_df['Fecha'].dt.to_period('M').dt.to_timestamp()
                                    elif aggregation_period == "year":
                                        filtered_df['Fecha_Agrupada'] = filtered_df['Fecha'].dt.to_period('Y').dt.to_timestamp()
                                    elif aggregation_period == "day":
                                        filtered_df['Fecha_Agrupada'] = filtered_df['Fecha'].dt.normalize()
                                    
                                    group_cols.append('Fecha_Agrupada')
                                    x_col_for_plot = 'Fecha_Agrupada'
                                else:
                                    if x_col:
                                        group_cols.append(x_col)
                                    
                                if color_col:
                                    group_cols.append(color_col)

                                if y_col and pd.api.types.is_numeric_dtype(filtered_df[y_col]):
                                    if group_cols:
                                        aggregated_df = filtered_df.groupby(group_cols, as_index=False)[y_col].sum()
                                    else:
                                        aggregated_df = filtered_df.copy()

                                    if x_col_for_plot == 'Fecha_Agrupada':
                                        aggregated_df = aggregated_df.sort_values(by='Fecha_Agrupada')
                                    elif x_col and x_col in aggregated_df.columns:
                                        aggregated_df = aggregated_df.sort_values(by=x_col)
                                else:
                                    st.warning(f"La columna '{y_col}' no es numérica y no se puede sumar para el gráfico. Mostrando datos sin agregar.")
                                    aggregated_df = filtered_df.copy()
                                    x_col_for_plot = x_col

                                if chart_data["chart_type"] == "line":
                                    fig = px.line(aggregated_df, x=x_col_for_plot, y=y_col, color=color_col,
                                                  title=f"Evolución de {y_col} por {x_col}",
                                                  labels={x_col_for_plot: x_col, y_col: y_col})
                                elif chart_data["chart_type"] == "bar":
                                    fig = px.bar(aggregated_df, x=x_col_for_plot, y=y_col, color=color_col,
                                                 title=f"Distribución de {y_col} por {x_col}",
                                                 labels={x_col_for_plot: x_col, y_col: y_col})

                            elif chart_data["chart_type"] == "pie":
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
                                if x_col and y_col and x_col in filtered_df.columns and y_col in filtered_df.columns:
                                    fig = px.scatter(filtered_df, x=x_col, y=y_col, color=color_col,
                                                     title=f"Relación entre {x_col} y {y_col}",
                                                     labels={x_col: x_col, y_col: y_col})
                                else:
                                    st.warning("Columnas necesarias para el gráfico de dispersión no encontradas. Mostrando el DataFrame filtrado.")
                                    st.dataframe(filtered_df)

                            elif chart_data["chart_type"] == "table":
                                st.subheader(chart_data.get("summary_response", "Aquí tienes la tabla solicitada:"))
                                
                                if table_columns:
                                    valid_table_columns = [col for col in table_columns if col in filtered_df.columns]
                                    if len(valid_table_columns) == len(table_columns):
                                        st.dataframe(filtered_df[valid_table_columns])
                                    else:
                                        st.warning(f"Algunas columnas solicitadas para la tabla no se encontraron: {', '.join(set(table_columns) - set(filtered_df.columns))}. Mostrando el DataFrame filtrado completo.")
                                        st.dataframe(filtered_df)
                                elif x_col and y_col and x_col in filtered_df.columns and y_col in filtered_df.columns:
                                    table_group_cols = [x_col]
                                    if color_col and color_col in filtered_df.columns:
                                        table_group_cols.append(color_col)
                                    
                                    if pd.api.types.is_numeric_dtype(filtered_df[y_col]):
                                        table_data = filtered_df.groupby(table_group_cols, as_index=False)[y_col].sum()
                                        st.dataframe(table_data)
                                    else:
                                        st.warning(f"La columna '{y_col}' no es numérica para agregar en la tabla. Mostrando el DataFrame filtrado completo.")
                                        st.dataframe(filtered_df)
                                else:
                                    st.dataframe(filtered_df)
                                
                                fig = "handled_as_table"

                            if fig and fig != "handled_as_table":
                                st.plotly_chart(fig, use_container_width=True)
                            elif fig is None and chart_data["chart_type"] != "table":
                                st.warning("No se pudo generar la visualización solicitada o los datos no son adecuados.")
                    else: # Si no es una solicitud de gráfico/tabla, procede con el análisis de texto
                        final_summary_response = chart_data.get("summary_response", "")
                        calculation_type = chart_data.get("calculation_type", "none")
                        calculation_params = chart_data.get("calculation_params", {})

                        # --- Realizar cálculos basados en calculation_type ---
                        if calculation_type == "total_sales":
                            total_monto_facturado = df["Monto Facturado"].sum()
                            final_summary_response = final_summary_response.replace("[TOTAL_MONTO_FACTURADO:.2f]", f"{total_monto_facturado:.2f}")

                        elif calculation_type == "max_client_sales":
                            # Actualizado a "Cliente"
                            if "Cliente" in df.columns and "Monto Facturado" in df.columns:
                                sales_by_client = df.groupby("Cliente")["Monto Facturado"].sum()
                                if not sales_by_client.empty:
                                    max_sales_client = sales_by_client.idxmax()
                                    max_sales_amount = sales_by_client.max()
                                    final_summary_response = final_summary_response.replace("[NOMBRE_CLIENTE_MAX_VENTAS]", str(max_sales_client))
                                    final_summary_response = final_summary_response.replace("[MONTO_MAX_VENTAS:.2f]", f"{max_sales_amount:.2f}")
                                else:
                                    final_summary_response = final_summary_response.replace("[NOMBRE_CLIENTE_MAX_VENTAS]", "No hay datos de clientes disponibles para este cálculo.")
                                    final_summary_response = final_summary_response.replace("[MONTO_MAX_VENTAS:.2f]", "N/A")
                            else:
                                final_summary_response = final_summary_response.replace("[NOMBRE_CLIENTE_MAX_VENTAS]", "N/A").replace("[MONTO_MAX_VENTAS:.2f]", "N/A")

                        elif calculation_type == "min_month_sales":
                            if "Fecha" in df.columns and "Monto Facturado" in df.columns:
                                df_monthly = df.set_index("Fecha").resample("M")["Monto Facturado"].sum()
                                if not df_monthly.empty:
                                    min_month_date = df_monthly.idxmin()
                                    min_month_name = min_month_date.strftime("%B %Y")
                                    min_month_amount = df_monthly.min()
                                    final_summary_response = final_summary_response.replace("[MES_MIN_INGRESOS]", min_month_name)
                                    final_summary_response = final_summary_response.replace("[MONTO_MIN_INGRESOS:.2f]", f"{min_month_amount:.2f}")
                                else:
                                    final_summary_response = final_summary_response.replace("[MES_MIN_INGRESOS]", "N/A").replace("[MONTO_MIN_INGRESOS:.2f]", "N/A")
                            else:
                                final_summary_response = final_summary_response.replace("[MES_MIN_INGRESOS]", "N/A").replace("[MONTO_MIN_INGRESOS:.2f]", "N/A")

                        elif calculation_type == "sales_for_period":
                            target_year = calculation_params.get("year")
                            target_month = calculation_params.get("month")
                            
                            calculated_sales = 0
                            if target_year and "Fecha" in df.columns and "Monto Facturado" in df.columns:
                                filtered_by_year = df[df["Fecha"].dt.year == target_year]
                                if target_month:
                                    filtered_by_month = filtered_by_year[filtered_by_year["Fecha"].dt.month == target_month]
                                    calculated_sales = filtered_by_month["Monto Facturado"].sum()
                                    final_summary_response = final_summary_response.replace("[CALCULATED_SALES_ENERO_2025:.2f]", f"{calculated_sales:.2f}") 
                                else:
                                    calculated_sales = filtered_by_year["Monto Facturado"].sum()
                                    final_summary_response = final_summary_response.replace("[CALCULATED_TOTAL_2024:.2f]", f"{calculated_sales:.2f}")
                            else:
                                final_summary_response = final_summary_response.replace("[CALCULATED_TOTAL_2024:.2f]", "N/A").replace("[CALCULATED_SALES_ENERO_2025:.2f]", "N/A")

                        elif calculation_type == "project_remaining_year":
                            target_year = calculation_params.get("target_year")
                            if target_year and "Fecha" in df.columns and "Monto Facturado" in df.columns:
                                current_date = datetime.now()
                                current_year = current_date.year
                                current_month = current_date.month

                                df_target_year = df[df["Fecha"].dt.year == target_year]
                                df_completed_months = df_target_year[df_target_year["Fecha"].dt.month <= current_month]

                                if not df_completed_months.empty:
                                    monthly_sales = df_completed_months.groupby(df_completed_months['Fecha'].dt.to_period('M'))['Monto Facturado'].sum()
                                    
                                    if not monthly_sales.empty:
                                        avg_monthly_sales = monthly_sales.mean()
                                    else:
                                        all_monthly_sales = df.groupby(df['Fecha'].dt.to_period('M'))['Monto Facturado'].sum()
                                        avg_monthly_sales = all_monthly_sales.mean() if not all_monthly_sales.empty else 0

                                    remaining_months = 12 - current_month
                                    projected_sales = avg_monthly_sales * remaining_months
                                    
                                    final_summary_response = final_summary_response.replace("[ESTIMACION_RESTO_2025:.2f]", f"{projected_sales:.2f}")
                                else:
                                    final_summary_response = final_summary_response.replace("[ESTIMACION_RESTO_2025:.2f]", "No hay suficientes datos para una estimación.")
                            else:
                                final_summary_response = final_summary_response.replace("[ESTIMACION_RESTO_2025:.2f]", "N/A")
                        
                        elif calculation_type == "project_remaining_year_monthly":
                            target_year = calculation_params.get("target_year")
                            if target_year and "Fecha" in df.columns and "Monto Facturado" in df.columns:
                                ts_data = df.set_index('Fecha')['Monto Facturado'].resample('MS').sum().fillna(0)
                                
                                current_date = datetime.now()
                                current_month = current_date.month

                                projected_months_list = []
                                
                                if len(ts_data) < 24: # Necesitamos al menos 2 años de datos para una buena estacionalidad mensual
                                    st.warning("Se necesitan al menos 2 años de datos mensuales para una proyección con estacionalidad precisa. Recurriendo a proyección basada en promedio simple.")
                                    avg_monthly_sales = ts_data.mean() if not ts_data.empty else 0
                                    
                                    for month_num in range(current_month + 1, 13):
                                        month_name = datetime(target_year, month_num, 1).strftime("%B")
                                        projected_months_list.append(f"- {month_name.capitalize()} {target_year}: ${avg_monthly_sales:.2f}")
                                    
                                    final_summary_response = final_summary_response.replace("[ESTIMACION_MENSUAL_RESTO_2025]", "\n" + "\n".join(projected_months_list))

                                else:
                                    try:
                                        decomposition = seasonal_decompose(ts_data, model='additive', period=12, extrapolate_trend='freq')
                                        trend = decomposition.trend
                                        seasonal = decomposition.seasonal

                                        for i in range(12 - current_month):
                                            future_date = current_date + relativedelta(months=i+1)
                                            future_month_num = future_date.month
                                            future_year = future_date.year

                                            seasonal_component = seasonal.iloc[(future_month_num - 1) % 12]

                                            if not trend.empty and not pd.isna(trend.iloc[-1]):
                                                current_trend_value = trend.iloc[-1]
                                            else:
                                                current_trend_value = trend.mean() if not trend.empty else ts_data.mean()

                                            projected_value = current_trend_value + seasonal_component
                                            
                                            month_name = future_date.strftime("%B")
                                            projected_months_list.append(f"- {month_name.capitalize()} {future_year}: ${max(0, projected_value):.2f}")

                                        if projected_months_list:
                                            monthly_projection_str = "\n" + "\n".join(projected_months_list)
                                            final_summary_response = final_summary_response.replace("[ESTIMACION_MENSUAL_RESTO_2025]", monthly_projection_str)
                                        else:
                                            final_summary_response = final_summary_response.replace("[ESTIMACION_MENSUAL_RESTO_2025]", "No hay meses restantes para proyectar en este año.")

                                    except Exception as e:
                                        st.error(f"Error al realizar la descomposición de series de tiempo: {e}. Asegúrate de tener suficientes datos históricos (al menos 2 años completos) para detectar estacionalidad mensual.")
                                        final_summary_response = final_summary_response.replace("[ESTIMACION_MENSUAL_RESTO_2025]", "No se pudo generar una estimación con estacionalidad debido a un error o falta de datos.")
                                        # Fallback a promedio simple if model fails
                                        avg_monthly_sales = ts_data.mean() if not ts_data.empty else 0
                                        projected_months_list = []
                                        for month_num in range(current_month + 1, 13):
                                            month_name = datetime(target_year, month_num, 1).strftime("%B")
                                            projected_months_list.append(f"- {month_name.capitalize()} {target_year}: ${avg_monthly_sales:.2f}")
                                        final_summary_response += "\n\nSe recurrió a una proyección basada en promedio simple." + "\n" + "\n".join(projected_months_list)

                            else:
                                final_summary_response = final_summary_response.replace("[ESTIMACION_MENSUAL_RESTO_2025]", "N/A")

                        elif calculation_type == "total_overdue_payments":
                            # Actualizado a "Estado Pago"
                            if "Estado Pago" in df.columns and "Monto Facturado" in df.columns:
                                # Asegúrate de que la columna 'Estado Pago' esté limpia y en el formato esperado
                                # Convertir a string y limpiar espacios
                                df['Estado Pago'] = df['Estado Pago'].astype(str).str.strip()
                                overdue_payments_df = df[df["Estado Pago"].str.contains("Vencido", case=False, na=False)]
                                total_overdue_monto = overdue_payments_df["Monto Facturado"].sum()
                                final_summary_response = final_summary_response.replace("[TOTAL_MONTO_VENCIDO:.2f]", f"{total_overdue_monto:.2f}")
                            else:
                                final_summary_response = final_summary_response.replace("[TOTAL_MONTO_VENCIDO:.2f]", "N/A")
                        
                        elif calculation_type == "recommendations":
                            # This block will handle the 'recommendations' type
                            # The summary_response from the first Gemini call will be empty,
                            # so we proceed to the second call with a detailed context for recommendations.
                            pass # No direct calculation here, just pass to the second Gemini call


                        # Si la summary_response de Gemini estaba vacía (indicando que se necesita un análisis profundo)
                        # o si no se pudo reemplazar un placeholder, hacer la segunda llamada a Gemini.
                        if not final_summary_response or "[NOMBRE_CLIENTE_MAX_VENTAS]" in final_summary_response or "[ESTIMACION_RESTO_2025:.2f]" in final_summary_response or "[ESTIMACION_MENSUAL_RESTO_2025]" in final_summary_response or "[TOTAL_MONTO_VENCIDO:.2f]" in final_summary_response:
                            contexto_analisis = f"""Eres un asesor financiero estratégico e impecable. Tu misión es proporcionar análisis de alto nivel, identificar tendencias, oportunidades y desafíos, y ofrecer recomendaciones estratégicas y accionables basadas en los datos disponibles.

                            **Resumen completo del DataFrame (para tu análisis):**
                            {df_summary_str}

                            **Columnas de datos disponibles y sus tipos (usa estos nombres EXACTOS):**
                            {available_columns_str}

                            Basándote **exclusivamente** en la información proporcionada en el resumen del DataFrame y en tu rol de analista financiero, por favor, responde a la siguiente pregunta del usuario.

                            Al formular tu respuesta, considera lo siguiente:
                            1.  **Análisis de Tendencias:** Identifica patrones de crecimiento, estancamiento o declive en los Montos Facturados.
                            2.  **Identificación de Oportunidades/Desafíos:** Basado en los datos (ej. Tipo Cliente con menos ventas, meses de bajo rendimiento, canales de venta, estado de pago), señala áreas de mejora o de potencial crecimiento.
                            3.  **Recomendaciones Estratégicas y Accionables:** Ofrece consejos prácticos y concretos que el usuario pueda implementar. Estas recomendaciones deben ser generales pero relevantes al contexto financiero y a la estructura de los datos. Sé proactivo en ofrecer ideas si la pregunta es general como "dame insights de mejora".
                            4.  **Tono:** Mantén un tono profesional, claro, conciso y empático.
                            5.  **Idioma:** Responde siempre en español.
                            6.  **Estructura:** Organiza tu respuesta con encabezados claros como "Análisis General", "Oportunidades Clave" y "Recomendaciones Estratégicas".

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
                                    "temperature": 0.5
                                }
                            }

                            with st.spinner("Consultando IA de Google Gemini para análisis y recomendaciones..."):
                                response = requests.post(api_url, headers={"Content-Type": "application/json"}, json=text_generation_payload)
                                if response.status_code == 200:
                                    response_data = response.json()
                                    if response_data and "candidates" in response_data and len(response_data["candidates"]) > 0:
                                        content = response_data["candidates"][0]["content"]["parts"][0]["text"]
                                        st.success("🤖 Respuesta de Gemini:")
                                        st.write(content)
                                    else:
                                        st.error("❌ No se recibió una respuesta válida de Gemini para el análisis.")
                                        st.text(response.text)
                                else:
                                    st.error(f"❌ Error al consultar Gemini API para análisis: {response.status_code}")
                                    st.text(response.text)
                        else:
                            st.success("🤖 Respuesta de Gemini:")
                            st.write(final_summary_response)

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
        elif consultar_button and not pregunta:
            st.warning("Por favor, ingresa una pregunta para consultar.")

        # Display history
        if st.session_state.question_history:
            st.subheader("Historial de Preguntas Recientes:")
            # Show most recent first
            for i, entry in enumerate(reversed(st.session_state.question_history)):
                st.write(f"- {entry}")
        else:
            st.info("Aún no has hecho ninguna pregunta.")


    except Exception as e:
        st.error("❌ No se pudo cargar la hoja de cálculo. Asegúrate de que la URL es correcta y las credenciales de Google Sheets están configuradas. También verifica que los nombres de las columnas en tu hoja coincidan con los esperados: 'Fecha', 'Monto Facturado', 'Tipo Cliente', 'Costo de Ventas', 'Gastos Operativos', 'Ingresos por Servicios', 'Canal de Venta', 'Estado Pago'.")
        st.exception(e)
