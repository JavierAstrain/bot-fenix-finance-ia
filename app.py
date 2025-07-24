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
if not st.session_state.logged_in:
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
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1mXxUmIQ44rd9escHOee2w0LxGs4MVNXaPrUeqj4USpk"

    try:
        sheet = client.open_by_url(SHEET_URL).sheet1
        data = sheet.get_all_values()
        df = pd.DataFrame(data[1:], columns=data[0])
        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
        df["Monto Facturado"] = pd.to_numeric(df["Monto Facturado"], errors="coerce")

        # Eliminar filas con valores NaN en columnas críticas para el análisis o gráficos
        df.dropna(subset=["Fecha", "Monto Facturado"], inplace=True)

        # --- Generar información dinámica de columnas para el prompt de Gemini ---
        available_columns_info = []
        for col in df.columns:
            col_type = df[col].dtype
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                available_columns_info.append(f"- '{col}' (tipo fecha, formato YYYY-MM-DD)")
            elif pd.api.types.is_numeric_dtype(df[col]):
                available_columns_info.append(f"- '{col}' (tipo numérico)")
            else:
                available_columns_info.append(f"- '{col}' (tipo texto)")
        available_columns_str = "\n".join(available_columns_info)


        # --- UI ---
        st.title("🤖 Bot Fénix Finance IA")
        st.write("Haz preguntas en lenguaje natural sobre tu información financiera.")
        st.subheader("📊 Vista previa:")
        st.dataframe(df.head(10))

        # --- Sección de "Qué puedes preguntar" ---
        with st.expander("💡 ¿Qué puedes preguntar y cuáles son los alcances de este bot?"):
            st.write("""
            Este bot de Fénix Finance IA está diseñado para ayudarte a analizar tus datos financieros. Puedes:

            * **Consultar Datos Específicos:**
                * Ej: "¿Cuál fue el Monto Facturado total en el mes de marzo de 2025?"
                * Ej: "¿Cuántas transacciones hubo en el año 2024?" (si tienes una columna de ID de transacción)

            * **Generar Gráficos Interactivos:**
                * **Evolución:** "Hazme un gráfico de línea con la evolución de Monto Facturado en 2023."
                * **Comparación:** "Muestra un gráfico de barras del Monto Facturado por mes."
                * **Segmentación:** "Crea un gráfico de evolución de ventas de 2025 separado por TipoCliente." (Requiere la columna 'TipoCliente' en tus datos)
                * **Rangos de Fecha:** "Gráfico de Monto Facturado entre 2024-01-15 y 2024-04-30."
                * **Tipos de Gráfico:** Línea, barras, pastel, dispersión.

            * **Realizar Análisis y Obtener Perspectivas:**
                * Ej: "¿Qué tendencias observas en mis Montos Facturados?"
                * Ej: "¿Hubo alguna anomalía en las ventas del último trimestre?"
                * Ej: "Dame un análisis de los datos de 2024."

            * **Hacer Estimaciones y Proyecciones (con cautela):**
                * Ej: "¿Podrías proyectar el Monto Facturado para el próximo mes basándote en los datos históricos?"
                * **Alcance:** Las proyecciones se basan **únicamente** en los datos históricos proporcionados y son estimaciones. **No son consejos financieros garantizados.**

            * **Recibir Recomendaciones Estratégicas:**
                * Ej: "¿Qué recomendaciones me darías para mejorar mi Monto Facturado?"
                * **Alcance:** Las recomendaciones se derivan del análisis de tus datos y buscan ofrecer ideas accionables. **Siempre consulta con un profesional financiero antes de tomar decisiones importantes.**

            **Importante:**
            * El bot solo puede analizar la información presente en tu hoja de cálculo.
            * Asegúrate de que los nombres de las columnas que mencionas en tus preguntas (ej. 'Fecha', 'Monto Facturado', 'TipoCliente') coincidan con los de tu hoja.
            * Para análisis avanzados o gráficos segmentados, es necesario que las columnas relevantes existan en tus datos.
            """)

        # --- NUEVA SECCIÓN: Verificación de API Key de Gemini ---
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
            # Se usa la clave de st.secrets directamente aquí para la operación principal
            try:
                google_gemini_api_key = st.secrets["GOOGLE_GEMINI_API_KEY"]
            except KeyError:
                st.error("❌ GOOGLE_GEMINI_API_KEY no encontrada en st.secrets. Por favor, configúrala en .streamlit/secrets.toml")
                st.stop()

            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={google_gemini_api_key}"

            # --- PRIMERA LLAMADA A GEMINI: DETECTAR INTENCIÓN DE GRÁFICO Y EXTRAER PARÁMETROS ---
            chart_detection_payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": f"""Analiza la siguiente pregunta del usuario y determina si solicita un gráfico.
                                Si es así, extrae el tipo de gráfico, las columnas para los ejes X e Y, una columna para colorear/agrupar (si se pide una segmentación), y cualquier filtro de fecha o valor.
                                Si no es una solicitud de gráfico, marca 'is_chart_request' como false.

                                **Columnas de datos disponibles y sus tipos:**
                                {available_columns_str}

                                **Consideraciones para la respuesta:**
                                - Para gráficos de evolución (línea), la columna del eje X debe ser una columna de tipo 'fecha'.
                                - Para gráficos de barras o de línea que muestren evolución, los datos del eje Y (ej: 'Monto Facturado') a menudo necesitan ser sumados por la unidad de tiempo del eje X (ej: por mes, por año).
                                - Si el usuario pide "separado por X", "por tipo de Y", o "por categoría Z", identifica la columna correspondiente para 'color_column'. Si no hay una columna obvia en los datos para esa segmentación, deja 'color_column' vacío.
                                - Si el usuario pide un rango de fechas (ej. "entre enero y marzo", "del 15 de marzo al 30 de abril"), extrae `start_date` y `end_date` en formato YYYY-MM-DD.
                                - Si el usuario pide filtrar por otra columna (ej. "solo para clientes particulares"), extrae esto en `additional_filters` como una lista de objetos.
                                - **IMPORTANTE:** Solo usa los nombres de columna que están explícitamente listados en "Columnas de datos disponibles". Si el usuario pide una columna que no existe, deja el campo vacío.

                                **Ejemplos de cómo mapear la intención (en formato JSON válido):**
                                - "evolución de ventas del año 2025": {{"is_chart_request": true, "chart_type": "line", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "Fecha", "filter_value": "2025", "color_column": "", "start_date": "", "end_date": "", "additional_filters": [], "summary_response": "Aquí tienes la evolución de ventas para el año 2025:"}}
                                - "ventas por mes": {{"is_chart_request": true, "chart_type": "bar", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "", "end_date": "", "additional_filters": [], "summary_response": "Aquí tienes un gráfico de barras de las ventas por mes:"}}
                                - "gráfico de barras de montos facturados por TipoCliente": {{"is_chart_request": true, "chart_type": "bar", "x_axis": "TipoCliente", "y_axis": "Monto Facturado", "filter_column": "", "filter_value": "", "color_column": "TipoCliente", "start_date": "", "end_date": "", "additional_filters": [], "summary_response": "Aquí tienes un gráfico de barras de los montos facturados por TipoCliente:"}}
                                - "creame un grafico con la evolucion de ventas de 2025 separado por particular y seguro": {{"is_chart_request": true, "chart_type": "line", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "Fecha", "filter_value": "2025", "color_column": "TipoCliente", "start_date": "", "end_date": "", "additional_filters": [], "summary_response": "Aquí tienes la evolución de ventas de 2025, separada por particular y seguro:"}}
                                - "ventas entre 2024-03-01 y 2024-06-30": {{"is_chart_request": true, "chart_type": "line", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "", "filter_value": "", "color_column": "", "start_date": "2024-03-01", "end_date": "2024-06-30", "additional_filters": [], "summary_response": "Aquí tienes la evolución de ventas entre marzo y junio de 2024:"}}
                                - "ventas de particular en el primer trimestre de 2025": {{"is_chart_request": true, "chart_type": "line", "x_axis": "Fecha", "y_axis": "Monto Facturado", "filter_column": "Fecha", "filter_value": "2025", "color_column": "", "start_date": "2025-01-01", "end_date": "2025-03-31", "additional_filters": [{{"column": "TipoCliente", "value": "particular"}}], "summary_response": "Aquí tienes las ventas de clientes particulares en el primer trimestre de 2025:"}}
                                - "analisis de mis ingresos": {{"is_chart_request": false, "chart_type": "none", "x_axis": "", "y_axis": "", "color_column": "", "filter_column": "", "filter_value": "", "start_date": "", "end_date": "", "additional_filters": [], "summary_response": ""}}

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
                                "description": "Respuesta conversacional si se genera un gráfico. Vacío si no es gráfico."
                            }
                        },
                        "required": ["is_chart_request", "chart_type", "x_axis", "y_axis", "color_column", "filter_column", "filter_value", "start_date", "end_date", "additional_filters", "summary_response"]
                    }
                }
            }

            try:
                with st.spinner("Analizando su solicitud y preparando el gráfico/análisis..."):
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
                            st.error("❌ La respuesta del modelo no contiene la estructura esperada para la detección de gráficos.")
                            st.text(f"Respuesta completa: {chart_response.text}")
                            st.stop()
                    else:
                        st.error(f"❌ Error al consultar Gemini API para detección de gráfico: {chart_response.status_code}")
                        st.text(chart_response.text)
                        st.stop()

                    if chart_data.get("is_chart_request"):
                        st.success(chart_data.get("summary_response", "Aquí tienes el gráfico solicitado:"))

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
                            st.warning("No hay datos para generar el gráfico con los filtros especificados.")
                        else:
                            x_col = chart_data.get("x_axis")
                            y_col = chart_data.get("y_axis")
                            color_col = chart_data.get("color_column")

                            # --- FIX: Asegurarse de que color_col sea None si es una cadena vacía ---
                            if color_col == "":
                                color_col = None

                            # Validar que las columnas existan en el DataFrame antes de usarlas
                            if x_col not in filtered_df.columns:
                                st.error(f"La columna '{x_col}' para el eje X no se encontró en los datos. Por favor, revisa el nombre de la columna en tu hoja de cálculo.")
                                st.stop()
                            if y_col not in filtered_df.columns:
                                st.error(f"La columna '{y_col}' para el eje Y no se encontró en los datos. Por favor, revisa el nombre de la columna en tu hoja de cálculo.")
                                st.stop()
                            # Si color_col no es None y no está en las columnas, advertir y establecer a None
                            if color_col is not None and color_col not in filtered_df.columns:
                                st.warning(f"La columna '{color_col}' para segmentación no se encontró en los datos. El gráfico no se segmentará. Por favor, revisa el nombre de la columna en tu hoja de cálculo.")
                                color_col = None # Ignorar la columna si no existe

                            # --- Agregación y ordenamiento para gráficos de línea/barras ---
                            group_cols = [x_col]
                            if color_col:
                                group_cols.append(color_col)

                            if x_col == "Fecha":
                                aggregated_df = filtered_df.copy()
                                # Agrupar por el período que tenga sentido, por ejemplo, por mes
                                aggregated_df['Fecha_Agrupada'] = aggregated_df['Fecha'].dt.to_period('M').dt.to_timestamp()
                                group_cols_for_agg = ['Fecha_Agrupada']
                                if color_col:
                                    group_cols_for_agg.append(color_col)
                                
                                # FIX: Usar as_index=False en groupby
                                aggregated_df = aggregated_df.groupby(group_cols_for_agg, as_index=False)[y_col].sum()
                                aggregated_df = aggregated_df.sort_values(by='Fecha_Agrupada')
                                x_col_for_plot = 'Fecha_Agrupada'
                            else:
                                # FIX: Usar as_index=False en groupby
                                aggregated_df = filtered_df.groupby(group_cols, as_index=False)[y_col].sum()
                                aggregated_df = aggregated_df.sort_values(by=x_col)
                                x_col_for_plot = x_col


                            fig = None
                            if chart_data["chart_type"] == "line":
                                fig = px.line(aggregated_df, x=x_col_for_plot, y=y_col, color=color_col,
                                              title=f"Evolución de {y_col} por {x_col}",
                                              labels={x_col_for_plot: x_col, y_col: y_col})
                            elif chart_data["chart_type"] == "bar":
                                fig = px.bar(aggregated_df, x=x_col_for_plot, y=y_col, color=color_col,
                                             title=f"Distribución de {y_col} por {x_col}",
                                             labels={x_col_for_plot: x_col, y_col: y_col})
                            elif chart_data["chart_type"] == "pie":
                                # Para gráficos de pastel, no se usa as_index=False en el groupby si names es la columna agrupada
                                # porque names espera una columna del DF original o del DF agrupado si ya se ha reseteado el índice.
                                # Aquí, agrupamos y luego usamos names=x_col, values=y_col
                                grouped_pie_df = filtered_df.groupby(x_col)[y_col].sum().reset_index()
                                fig = px.pie(grouped_pie_df, names=x_col, values=y_col,
                                             title=f"Proporción de {y_col} por {x_col}")
                            elif chart_data["chart_type"] == "scatter":
                                fig = px.scatter(filtered_df, x=x_col, y=y_col, color=color_col,
                                                 title=f"Relación entre {x_col} y {y_col}",
                                                 labels={x_col: x_col, y_col: y_col})

                            if fig:
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.warning("No se pudo generar el tipo de gráfico solicitado o los datos no son adecuados.")
                    else: # Si no es una solicitud de gráfico, procede con el análisis de texto
                        # --- SEGUNDA LLAMADA A GEMINI: ANÁLISIS Y RECOMENDACIONES (con mejoras) ---
                        contexto_analisis = f"""Eres un asistente de IA especializado en análisis financiero. Tu misión es ayudar al usuario a interpretar sus datos, identificar tendencias, predecir posibles escenarios (con cautela) y ofrecer recomendaciones estratégicas.

                        Aquí están las **primeras 20 filas** de los datos financieros disponibles para tu análisis:

                        {df.head(20).to_string(index=False)}

                        **Columnas de datos disponibles y sus tipos:**
                        {available_columns_str}

                        Basándote **exclusivamente** en la información proporcionada y en tu rol de analista financiero, por favor, responde a la siguiente pregunta del usuario.

                        Al formular tu respuesta, considera lo siguiente:
                        1.  **Análisis Profundo:** Busca patrones, anomalías, crecimientos o decrecimientos significativos. Identifica y destaca cualquier punto clave (máximos, mínimos, cambios abruptos) relevantes para la pregunta. Si es posible, menciona métricas clave o porcentajes de cambio.
                        2.  **Predicción (si aplica):** Si la pregunta sugiere una proyección, basa tu estimación en las tendencias históricas visibles en los datos. **IMPORTANTE: Siempre aclara que cualquier predicción es una estimación basada en datos pasados y no una garantía ni un consejo financiero.**
                        3.  **Recomendaciones Accionables:** Ofrece consejos prácticos y accionables que el usuario pueda considerar para mejorar su situación financiera, siempre fundamentados en el análisis de los datos.
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
