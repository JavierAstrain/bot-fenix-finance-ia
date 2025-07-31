import streamlit as st
import pandas as pd
import gspread
import json
import requests
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime
import numpy as np
from dateutil.relativedelta import relativedelta
from io import StringIO
import re

# --- Configuración de Login ---
# No cambies estas credenciales en el código. Para un uso real, usa st.secrets.
USERNAME = "javi"
PASSWORD = "javi"

# Inicializar el estado de la sesión para el login y el historial de preguntas
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
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")

# Mostrar el formulario de login si el usuario no ha iniciado sesión
if not st.session_state.logged_in:
    show_login_form()
else:
    # --- AGREGAR LOGO DE LA EMPRESA Y TÍTULO ---
    col_title, col_logo = st.columns([0.7, 0.3])

    with col_title:
        st.title("🤖 Bot Fénix Finance IA")

    with col_logo:
        try:
            # Reemplaza 'logo.png' con el nombre de tu archivo de logo
            st.image("https://placehold.co/150x150/000000/FFFFFF?text=LOGO", width=150)
        except FileNotFoundError:
            st.warning("No se encontró el archivo de logo.")

    st.write("Haz preguntas en lenguaje natural sobre tu información financiera.")

    # --- CREDENCIALES GOOGLE DESDE SECRETS ---
    try:
        creds_dict = st.secrets["GOOGLE_CREDENTIALS"]
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
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1SaXuzhY_sJ9Tk9MOLDLAI4OVdsNbCP-X4L8cP15yTqo/edit?gid=1865408530#gid=1865408530"

    @st.cache_data(ttl=600)  # Cachea los datos por 10 minutos
    def load_data(url):
        try:
            workbook = client.open_by_url(url)
            all_data = []
            
            # Puedes ajustar el rango (ej. worksheets()[0:2]) para leer más o menos hojas
            # Aquí leemos las primeras 4 hojas, si existen.
            sheets_to_read = workbook.worksheets()[:4]
            
            for sheet in sheets_to_read:
                st.info(f"Cargando datos de la hoja: **{sheet.title}**")
                data = sheet.get_all_values()
                if not data:
                    st.warning(f"La hoja '{sheet.title}' está vacía. Saltando.")
                    continue

                # El primer row es el encabezado
                headers = data[0]
                rows = data[1:]

                df_sheet = pd.DataFrame(rows, columns=headers)
                df_sheet['Source_Sheet'] = sheet.title # Agregar una columna para identificar la hoja de origen
                all_data.append(df_sheet)

            if not all_data:
                st.error("⚠️ No se encontraron datos en las hojas de cálculo.")
                return pd.DataFrame()

            # Combina todos los DataFrames en uno solo
            df = pd.concat(all_data, ignore_index=True)
            return df

        except gspread.exceptions.APIError as e:
            st.error(f"❌ Error de la API de Google Sheets. Asegúrate de que la cuenta de servicio tenga acceso a la planilla. Detalle: {e}")
            return pd.DataFrame()
        except Exception as e:
            st.error("❌ Error al cargar los datos desde la hoja de cálculo. Por favor, verifica la URL y tus credenciales.")
            st.exception(e)
            return pd.DataFrame()

    df = load_data(SHEET_URL)

    if not df.empty:
        # --- Limpiar nombres de columnas (eliminar espacios en blanco alrededor) ---
        df.columns = df.columns.str.strip()

        # --- AQUI PUEDES RENOMLBRAR COLUMNAS PARA UNIFICARLAS ---
        # Si las columnas de tus 4 hojas tienen nombres diferentes pero representan lo mismo,
        # renómbralas aquí. Por ejemplo:
        # df.rename(columns={'Monto total': 'Monto Facturado', 'ValorVenta': 'Monto Facturado'}, inplace=True)
        
        # Define los nombres de las columnas esenciales que esperas.
        # ** IMPORTANTE: DEBES ACTUALIZAR ESTA LISTA CON LOS NOMBRES EXACTOS DE TUS COLUMNAS COMBINADAS **
        required_columns = ["Fecha", "Monto Facturado", "Cliente", "Tipo Cliente", "Sucursal", "Estado Pago", "Observaciones"]
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            st.error(f"❌ Faltan columnas esenciales en tu hoja de cálculo combinada: {', '.join(missing_columns)}. Por favor, asegura que todas las hojas tienen estas columnas o renómbralas en el código para que coincidan.")
            st.stop()

        # --- Limpieza y conversión de datos ---
        # El bot necesita estas columnas para funcionar correctamente.
        try:
            # Convierte 'Fecha' a formato de fecha
            df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce", dayfirst=True)
            
            # Limpieza y conversión de 'Monto Facturado'
            if 'Monto Facturado' in df.columns:
                df['Monto Facturado'] = df['Monto Facturado'].astype(str)
                df['Monto Facturado'] = df['Monto Facturado'].str.replace(r'[$,.]', '', regex=True)
                df['Monto Facturado'] = df['Monto Facturado'].str.replace(',', '.', regex=False)
                df['Monto Facturado'] = pd.to_numeric(df['Monto Facturado'], errors="coerce")

            # Elimina filas con valores NaN en columnas críticas
            df.dropna(subset=["Fecha", "Monto Facturado"], inplace=True)

        except Exception as e:
            st.error(f"❌ Error al procesar los datos después de la carga. Por favor, verifica el formato de las columnas 'Fecha' y 'Monto Facturado'.")
            st.exception(e)
            st.stop()
            
        # --- Verificar si el DataFrame está vacío después de la limpieza ---
        if df.empty:
            st.error("⚠️ Después de cargar y limpiar los datos, no se encontraron filas válidas con 'Fecha' y 'Monto Facturado'. Por favor, revisa tu hoja de cálculo.")
            st.stop()

        # --- Mostrar vista previa de los datos después de la carga y limpieza ---
        st.subheader("📊 Vista previa de los datos combinados:")
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
                        st.error("❌ La solicitud a la API de Gemini ha excedido el tiempo de espera (timeout).")
                    except requests.exceptions.ConnectionError:
                        st.error("❌ Error de conexión a la API de Gemini.")
                    except json.JSONDecodeError:
                        st.error("❌ La respuesta de la API no es un JSON válido.")
                    except Exception as e:
                        st.error(f"❌ Ocurrió un error inesperado: {e}")

        st.subheader("💬 ¿Qué deseas saber?")
        pregunta = st.text_input("Ej: ¿Cuáles fueron las ventas del año 2025? o Hazme un gráfico de la evolución de ventas del 2025.")
        consultar_button = st.button("Consultar")

        if consultar_button and pregunta:
            # Add current question to history
            st.session_state.question_history.append(pregunta)
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
                                "text": f"""Eres un asesor financiero y de gestión de negocios. Tu objetivo es proporcionar análisis precisos, gráficos claros y respuestas directas, útiles y accionables.

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
-   `chart_type`: String. Tipo de visualización (line, bar, pie, scatter, table). 'none' si no es gráfico.
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
-   "total de pagos atrasados": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "Estado Pago", "filter_value": "Atrasado", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "El total de pagos atrasados es de $[TOTAL_ATRASADO].", "aggregation_period": "none", "table_columns": [], "calculation_type": "total_overdue_payments", "calculation_params": {{}}}}
-   "cuál es el porcentaje de ventas de Tipo Cliente 'particular'": {{"is_chart_request": false, "chart_type": "pie", "x_axis": "Tipo Cliente", "y_axis": "Monto Facturado", "filter_column": "", "filter_value": "", "color_column": "Tipo Cliente", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "El porcentaje de ventas para el Tipo Cliente 'particular' es del [PERCENTAGE]% del total.", "aggregation_period": "none", "table_columns": [], "calculation_type": "percentage_of_total_sales_by_category", "calculation_params": {{"category": "Tipo Cliente", "value": "particular"}}}}
-   "recomendaciones para mejorar ventas": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": [], "additional_filters": [], "summary_response": "Basado en los datos, aquí tienes algunas recomendaciones:", "aggregation_period": "none", "table_columns": [], "calculation_type": "recommendations", "calculation_params": {{}}}}

La pregunta del usuario es: "{pregunta}"
Quiero que me respondas en un formato JSON válido y sin texto adicional.

"""
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "responseMimeType": "application/json"
                }
            }
            
            with st.spinner("🤖 Analizando tu pregunta..."):
                response = requests.post(api_url, headers={"Content-Type": "application/json"}, json=chart_detection_payload, timeout=20)
            
            try:
                response_json = response.json()
                if "candidates" not in response_json or not response_json["candidates"]:
                    st.error("❌ El modelo no generó una respuesta válida. Intenta de nuevo.")
                    st.json(response_json)
                    st.stop()
                
                # Extraer y limpiar la cadena JSON
                response_text = response_json["candidates"][0]["content"]["parts"][0]["text"]
                # A veces el modelo devuelve código, limpiar si es necesario
                cleaned_json_str = response_text.strip().replace("```json\n", "").replace("```", "")
                llm_response = json.loads(cleaned_json_str)

            except json.JSONDecodeError as e:
                st.error(f"❌ Error al decodificar la respuesta JSON del modelo. La respuesta fue: {response_text}. Error: {e}")
                st.write("Respuesta completa del modelo (sin decodificar):")
                st.text(response_text)
                st.stop()
            except Exception as e:
                st.error(f"❌ Ocurrió un error inesperado al procesar la respuesta del modelo: {e}")
                st.stop()
                
            # --- Procesa los filtros y parámetros del LLM ---
            filtered_df = df.copy()

            if llm_response.get('filter_column') and llm_response.get('filter_value'):
                col_to_filter = llm_response['filter_column']
                val_to_filter = llm_response['filter_value']
                
                if pd.api.types.is_datetime64_any_dtype(filtered_df[col_to_filter]):
                    # Si el valor es un año (string de 4 dígitos)
                    if re.match(r'^\d{4}$', str(val_to_filter)):
                        filtered_df = filtered_df[filtered_df[col_to_filter].dt.year == int(val_to_filter)]
                    # Si es un nombre de mes, intenta convertirlo a número
                    elif val_to_filter.lower() in ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']:
                        mes_map = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12}
                        month_num = mes_map.get(val_to_filter.lower())
                        if month_num:
                            filtered_df = filtered_df[filtered_df[col_to_filter].dt.month == month_num]

            if llm_response.get('start_date') and llm_response.get('end_date'):
                try:
                    start_date = pd.to_datetime(llm_response['start_date'])
                    end_date = pd.to_datetime(llm_response['end_date'])
                    filtered_df = filtered_df[
                        (filtered_df['Fecha'] >= start_date) & 
                        (filtered_df['Fecha'] <= end_date)
                    ]
                except ValueError:
                    st.error("Error en el formato de fecha proporcionado. Usa YYYY-MM-DD.")
                    st.stop()
            
            # Procesar filtros adicionales
            if llm_response.get('additional_filters'):
                for filter_obj in llm_response['additional_filters']:
                    col = filter_obj['column']
                    val = filter_obj['value']
                    if col in filtered_df.columns:
                        filtered_df = filtered_df[filtered_df[col].astype(str).str.lower() == str(val).lower()]
            
            # --- Lógica para realizar los cálculos y generar la respuesta final ---
            if llm_response['is_chart_request']:
                st.markdown(f"### {llm_response['summary_response']}")

                if filtered_df.empty:
                    st.warning("No se encontraron datos para los filtros aplicados.")
                    st.stop()

                if llm_response['chart_type'] == 'table':
                    if llm_response['table_columns']:
                        st.dataframe(filtered_df[llm_response['table_columns']].head(100))
                    else:
                        st.dataframe(filtered_df.head(100))

                elif llm_response['chart_type'] in ['line', 'bar', 'pie', 'scatter']:
                    # Agrupar datos si se pide un periodo de agregación
                    if llm_response['aggregation_period'] in ['month', 'year']:
                        agg_period = 'M' if llm_response['aggregation_period'] == 'month' else 'Y'
                        
                        if 'Monto Facturado' in filtered_df.columns and pd.api.types.is_numeric_dtype(filtered_df['Monto Facturado']):
                            aggregated_df = filtered_df.set_index('Fecha').resample(agg_period)['Monto Facturado'].sum().reset_index()
                        else:
                            st.warning("La columna 'Monto Facturado' no es numérica o no está presente para la agregación.")
                            st.stop()
                        
                        aggregated_df['Fecha'] = aggregated_df['Fecha'].dt.strftime('%Y-%m') # Formato para gráfico
                        
                        if llm_response['color_column']:
                            # Si hay una columna de color, se necesita agrupar por ambos
                            aggregated_df = filtered_df.groupby([pd.Grouper(key='Fecha', freq=agg_period), llm_response['color_column']])['Monto Facturado'].sum().reset_index()
                            aggregated_df['Fecha'] = aggregated_df['Fecha'].dt.strftime('%Y-%m')
                        
                        data_to_plot = aggregated_df
                    else:
                        data_to_plot = filtered_df

                    # Generar el gráfico
                    try:
                        if llm_response['chart_type'] == 'line':
                            fig = px.line(data_to_plot, x=llm_response['x_axis'], y=llm_response['y_axis'], color=llm_response['color_column'], title=llm_response['summary_response'])
                        elif llm_response['chart_type'] == 'bar':
                            fig = px.bar(data_to_plot, x=llm_response['x_axis'], y=llm_response['y_axis'], color=llm_response['color_column'], title=llm_response['summary_response'])
                        elif llm_response['chart_type'] == 'pie':
                            fig = px.pie(data_to_plot, names=llm_response['x_axis'], values=llm_response['y_axis'], title=llm_response['summary_response'])
                        elif llm_response['chart_type'] == 'scatter':
                            fig = px.scatter(data_to_plot, x=llm_response['x_axis'], y=llm_response['y_axis'], color=llm_response['color_column'], title=llm_response['summary_response'])

                        st.plotly_chart(fig, use_container_width=True)
                    except Exception as e:
                        st.error(f"❌ No se pudo generar el gráfico. Asegúrate de que las columnas '{llm_response['x_axis']}' y '{llm_response['y_axis']}' existan en los datos filtrados y sean del tipo correcto.")
                        st.exception(e)

            else: # Es una respuesta textual o de cálculo
                st.markdown(f"### 🤖 Respuesta del Asesor:")
                st.info(llm_response['summary_response'])
                
                # --- Lógica para Cálculos Específicos ---
                calculation_type = llm_response.get('calculation_type')
                calculation_params = llm_response.get('calculation_params', {})
                
                if calculation_type == 'total_sales':
                    total_sales = filtered_df['Monto Facturado'].sum()
                    st.success(f"El monto total facturado es de **${total_sales:,.2f}**.")
                
                elif calculation_type == 'sales_for_period':
                    period_sales = filtered_df['Monto Facturado'].sum()
                    st.success(f"Las ventas para el periodo seleccionado son de **${period_sales:,.2f}**.")
                
                elif calculation_type == 'max_client_sales':
                    if 'Cliente' in filtered_df.columns and 'Monto Facturado' in filtered_df.columns:
                        client_sales = filtered_df.groupby('Cliente')['Monto Facturado'].sum().sort_values(ascending=False)
                        if not client_sales.empty:
                            max_client = client_sales.index[0]
                            max_sales = client_sales.iloc[0]
                            st.success(f"El cliente con la mayor cantidad de ventas es **{max_client}** con un total de **${max_sales:,.2f}**.")
                        else:
                            st.warning("No se pudieron encontrar las ventas por cliente.")
                    else:
                        st.warning("Faltan las columnas 'Cliente' o 'Monto Facturado' para realizar este cálculo.")

                elif calculation_type == 'min_month_sales':
                    if 'Fecha' in filtered_df.columns and 'Monto Facturado' in filtered_df.columns:
                        monthly_sales = filtered_df.set_index('Fecha')['Monto Facturado'].resample('M').sum()
                        if not monthly_sales.empty:
                            min_month = monthly_sales.idxmin()
                            min_sales = monthly_sales.min()
                            st.success(f"El mes con menos ingresos fue **{min_month.strftime('%B de %Y')}** con un total de **${min_sales:,.2f}**.")
                        else:
                            st.warning("No se pudieron encontrar las ventas mensuales.")
                    else:
                        st.warning("Faltan las columnas 'Fecha' o 'Monto Facturado' para realizar este cálculo.")
                
                elif calculation_type == 'total_overdue_payments':
                    if 'Estado Pago' in filtered_df.columns and 'Monto Facturado' in filtered_df.columns:
                        overdue_payments_df = filtered_df[filtered_df['Estado Pago'].str.lower() == 'atrasado']
                        total_overdue = overdue_payments_df['Monto Facturado'].sum()
                        st.success(f"El total de pagos atrasados es de **${total_overdue:,.2f}**.")
                    else:
                        st.warning("Faltan las columnas 'Estado Pago' o 'Monto Facturado' para realizar este cálculo.")
                
                elif calculation_type == 'percentage_of_total_sales_by_category':
                    category_col = calculation_params.get('category')
                    category_val = calculation_params.get('value')
                    if category_col in filtered_df.columns and 'Monto Facturado' in filtered_df.columns:
                        total_sales = filtered_df['Monto Facturado'].sum()
                        if total_sales > 0:
                            category_sales = filtered_df[filtered_df[category_col].astype(str).str.lower() == str(category_val).lower()]['Monto Facturado'].sum()
                            percentage = (category_sales / total_sales) * 100
                            st.success(f"El porcentaje de ventas para '{category_val}' es del **{percentage:,.2f}%** del total.")
                        else:
                            st.warning("El monto total de ventas es cero, no se puede calcular el porcentaje.")
                    else:
                        st.warning(f"Faltan las columnas '{category_col}' o 'Monto Facturado' para realizar este cálculo.")

                elif calculation_type == 'project_remaining_year':
                    if 'Fecha' in filtered_df.columns and 'Monto Facturado' in filtered_df.columns:
                        target_year = calculation_params.get('target_year', datetime.now().year)
                        
                        # Agregación mensual de los datos históricos
                        monthly_sales = filtered_df.set_index('Fecha')['Monto Facturado'].resample('M').sum()
                        
                        # Determinar el último mes con datos
                        last_month_with_data = monthly_sales.index.max()
                        
                        if last_month_with_data and last_month_with_data.year == target_year:
                            months_in_year = pd.date_range(start=f'{target_year}-01-01', end=f'{target_year}-12-31', freq='M')
                            months_with_data = monthly_sales.loc[f'{target_year}-01-01':last_month_with_data]
                            
                            # Si hay suficientes datos históricos
                            if len(monthly_sales) >= 12: # Al menos un año para calcular la estacionalidad
                                from statsmodels.tsa.seasonal import seasonal_decompose
                                
                                # Descomposición de la serie de tiempo para encontrar la estacionalidad
                                try:
                                    decomposition = seasonal_decompose(monthly_sales.dropna(), model='multiplicative', period=12)
                                    seasonal_component = decomposition.seasonal
                                except Exception:
                                    st.warning("No hay suficientes datos o los datos no son adecuados para la descomposición estacional. Se realizará una proyección simple basada en el promedio histórico.")
                                    seasonal_component = None

                                # Calcular promedio mensual sin estacionalidad
                                avg_monthly_sales = monthly_sales.mean()
                                
                                # Proyectar los meses restantes
                                remaining_months = [m for m in months_in_year if m > last_month_with_data]
                                projected_sales_list = []
                                for month in remaining_months:
                                    if seasonal_component is not None:
                                        # Usar el componente estacional para la proyección
                                        seasonal_factor = seasonal_component.loc[month - pd.offsets.DateOffset(years=1) if month.year > seasonal_component.index.min().year else month]
                                        projected_sales = avg_monthly_sales * seasonal_factor
                                    else:
                                        projected_sales = avg_monthly_sales # Proyección simple
                                    projected_sales_list.append(projected_sales)
                                
                                total_projected_sales = sum(projected_sales_list)
                                st.success(f"La estimación de ventas para el resto del año {target_year} es de aproximadamente **${total_projected_sales:,.2f}**.")
                                st.write("Esta proyección se basa en la estacionalidad y el promedio de tus datos históricos.")
                            else:
                                # Proyección simple si no hay suficientes datos
                                avg_monthly_sales_year = months_with_data.mean()
                                months_to_project = 12 - len(months_with_data)
                                total_projected_sales = avg_monthly_sales_year * months_to_project
                                st.success(f"La estimación de ventas para el resto del año {target_year} es de aproximadamente **${total_projected_sales:,.2f}**.")
                                st.write("Esta es una proyección simple basada en el promedio de los meses con datos del año actual.")
                        else:
                            st.warning(f"No se encontraron datos para el año {target_year}. No se puede realizar la proyección.")
                    else:
                        st.warning("Faltan las columnas 'Fecha' o 'Monto Facturado' para realizar este cálculo.")
                
                elif calculation_type == 'project_remaining_year_monthly':
                    if 'Fecha' in filtered_df.columns and 'Monto Facturado' in filtered_df.columns:
                        target_year = calculation_params.get('target_year', datetime.now().year)
                        
                        monthly_sales = filtered_df.set_index('Fecha')['Monto Facturado'].resample('M').sum()
                        last_month_with_data = monthly_sales.index.max()
                        
                        if last_month_with_data and last_month_with_data.year == target_year:
                            months_in_year = pd.date_range(start=f'{target_year}-01-01', end=f'{target_year}-12-31', freq='M')
                            
                            if len(monthly_sales) >= 12:
                                from statsmodels.tsa.seasonal import seasonal_decompose
                                try:
                                    decomposition = seasonal_decompose(monthly_sales.dropna(), model='multiplicative', period=12)
                                    seasonal_component = decomposition.seasonal
                                except Exception:
                                    seasonal_component = None
                                
                                avg_monthly_sales = monthly_sales.mean()
                                
                                projected_df = pd.DataFrame(columns=['Mes', 'Venta Proyectada'])
                                for month in months_in_year:
                                    if month > last_month_with_data:
                                        if seasonal_component is not None:
                                            seasonal_factor = seasonal_component.loc[month - pd.offsets.DateOffset(years=1) if month.year > seasonal_component.index.min().year else month]
                                            projected_sales = avg_monthly_sales * seasonal_factor
                                        else:
                                            projected_sales = avg_monthly_sales
                                        
                                        projected_df.loc[len(projected_df)] = [month.strftime('%Y-%m'), projected_sales]
                                
                                if not projected_df.empty:
                                    st.subheader(f"Proyección de ventas mensuales para el resto de {target_year}:")
                                    st.dataframe(projected_df)
                                    st.write("Esta proyección se basa en la estacionalidad y el promedio de tus datos históricos.")
                                    # Generar un gráfico de barras con la proyección
                                    fig = px.bar(projected_df, x='Mes', y='Venta Proyectada', title=f'Proyección de Ventas Mensuales {target_year}')
                                    st.plotly_chart(fig, use_container_width=True)
                                else:
                                    st.warning(f"No hay meses restantes en el año {target_year} para proyectar.")
                            else:
                                st.warning("No hay suficientes datos históricos (mínimo 12 meses) para realizar una proyección mensual con estacionalidad.")
                        else:
                            st.warning(f"No se encontraron datos para el año {target_year}. No se puede realizar la proyección.")
                    else:
                        st.warning("Faltan las columnas 'Fecha' o 'Monto Facturado' para realizar este cálculo.")

                elif calculation_type == 'recommendations':
                    # Lógica de recomendaciones basada en los datos.
                    # Esto es un ejemplo y puede ser expandido.
                    st.info("Basado en el análisis de tus datos, aquí hay algunas recomendaciones estratégicas:")
                    
                    # 1. Recomendación basada en el cliente con mayores ventas
                    if 'Cliente' in df.columns and 'Monto Facturado' in df.columns:
                        client_sales = df.groupby('Cliente')['Monto Facturado'].sum().sort_values(ascending=False)
                        if not client_sales.empty:
                            top_client = client_sales.index[0]
                            st.write(f"- **Foco en Clientes Clave:** El cliente **{top_client}** es tu principal fuente de ingresos. Considera estrategias para fortalecer esta relación, como programas de fidelización o ofertas personalizadas.")
                    
                    # 2. Recomendación basada en la sucursal con menos ventas
                    if 'Sucursal' in df.columns and 'Monto Facturado' in df.columns:
                        branch_sales = df.groupby('Sucursal')['Monto Facturado'].sum().sort_values()
                        if len(branch_sales) > 1 and not branch_sales.empty:
                            lowest_branch = branch_sales.index[0]
                            st.write(f"- **Mejora en Sucursales:** La sucursal **{lowest_branch}** muestra las ventas más bajas. Podría ser beneficioso analizar las causas, como falta de personal, capacitación, marketing o problemas de inventario, para implementar mejoras.")

                    # 3. Recomendación basada en el estado de pago
                    if 'Estado Pago' in df.columns and 'Monto Facturado' in df.columns:
                        overdue_df = df[df['Estado Pago'].str.lower() == 'atrasado']
                        total_overdue = overdue_df['Monto Facturado'].sum()
                        if total_overdue > 0:
                            st.write(f"- **Gestión de Cobranza:** Se ha identificado un total de **${total_overdue:,.2f}** en pagos atrasados. Es crucial establecer un proceso de seguimiento de cobranza más proactivo para mejorar el flujo de caja.")

                    st.write("\n_Recuerda que estas son sugerencias automáticas. Para decisiones importantes, consulta siempre con un experto._")
                
                else:
                    st.warning("Tipo de cálculo no reconocido. Proporcionando la respuesta textual del modelo.")
                    # El summary_response ya está impreso, no es necesario volver a hacerlo.

    else:
        st.warning("No hay datos para procesar. Por favor, asegúrate de que tu hoja de cálculo esté accesible y contenga datos.")

