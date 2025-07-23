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

    # --- IMPORTANTE: Si tu DataFrame tiene una columna para 'particular' y 'seguro',
    # asegúrate de que su nombre sea reconocido por Gemini en el prompt.
    # Por ejemplo, si la columna se llama 'TipoCliente', asegúrate de que Gemini la pueda identificar.
    # df["TipoCliente"] = df["TipoCliente"].astype(str) # Descomenta y ajusta si tienes esta columna

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
                            Si es así, extrae el tipo de gráfico, las columnas para los ejes X e Y, una columna para colorear/agrupar (si se pide una segmentación), y cualquier filtro de fecha o valor.
                            Si no es una solicitud de gráfico, marca 'is_chart_request' como false.

                            **Columnas de datos disponibles y sus tipos:**
                            - 'Fecha' (tipo fecha)
                            - 'Monto Facturado' (tipo numérico)
                            - **IMPORTANTE:** Si tu hoja de cálculo tiene una columna con valores como 'particular' y 'seguro' (por ejemplo, 'TipoCliente' o 'Segmento'), menciónala aquí para que Gemini la pueda usar como 'color_column'. Si no existe, omítela.

                            **Consideraciones para la respuesta:**
                            - Para gráficos de evolución (línea), la columna del eje X debe ser 'Fecha'.
                            - Para gráficos de barras o de línea que muestren evolución, los datos del eje Y ('Monto Facturado') a menudo necesitan ser sumados por la unidad de tiempo del eje X (ej: por mes, por año).
                            - Si el usuario pide "separado por X", "por tipo de Y", o "por categoría Z", identifica la columna correspondiente para 'color_column'. Si no hay una columna obvia en los datos para esa segmentación, deja 'color_column' vacío.

                            **Ejemplos de cómo mapear la intención:**
                            - "evolución de ventas del año 2025": chart_type='line', x_axis='Fecha', y_axis='Monto Facturado', filter_column='Fecha', filter_value='2025', color_column=''
                            - "ventas por mes": chart_type='bar', x_axis='Fecha', y_axis='Monto Facturado', filter_column='', filter_value='', color_column=''
                            - "gráfico de barras de montos facturados por tipo de cliente": chart_type='bar', x_axis='TipoCliente', y_axis='Monto Facturado', filter_column='', filter_value='', color_column='TipoCliente'
                            - "creame un grafico con la evolucion de ventas de 2025 separado por particular y seguro": chart_type='line', x_axis='Fecha', y_axis='Monto Facturado', filter_column='Fecha', filter_value='2025', color_column='TipoCliente' (asumiendo 'TipoCliente' existe y contiene 'particular' y 'seguro')

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
                    "required": ["is_chart_request", "chart_type", "x_axis", "y_axis", "color_column", "filter_column", "filter_value", "summary_response"]
                }
            }
        }

        try:
            with st.spinner("Analizando su solicitud y preparando el gráfico..."):
                chart_response = requests.post(api_url, headers={"Content-Type": "application/json"}, json=chart_detection_payload)
                chart_data_raw = chart_response.json()["candidates"][0]["content"]["parts"][0]["text"]
                chart_data = json.loads(chart_data_raw) # Parsear el JSON

            if chart_data.get("is_chart_request"):
                st.success(chart_data.get("summary_response", "Aquí tienes el gráfico solicitado:"))

                filtered_df = df.copy()

                # Aplicar filtro si existe
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
                                st.warning(f"No se pudo aplicar el filtro de fecha '{chart_data['filter_value']}'. Mostrando todos los datos relevantes.")
                    else:
                        # Para otros tipos de columnas de filtro
                        filtered_df = filtered_df[filtered_df[chart_data["filter_column"]].astype(str).str.contains(chart_data["filter_value"], case=False, na=False)]

                # Asegurarse de que haya datos después de filtrar
                if filtered_df.empty:
                    st.warning("No hay datos para generar el gráfico con los filtros especificados.")
                else:
                    x_col = chart_data.get("x_axis")
                    y_col = chart_data.get("y_axis")
                    color_col = chart_data.get("color_column")

                    # Validar que las columnas existan en el DataFrame antes de usarlas
                    if x_col not in filtered_df.columns:
                        st.error(f"La columna '{x_col}' para el eje X no se encontró en los datos.")
                        st.stop()
                    if y_col not in filtered_df.columns:
                        st.error(f"La columna '{y_col}' para el eje Y no se encontró en los datos.")
                        st.stop()
                    if color_col and color_col not in filtered_df.columns:
                        st.warning(f"La columna '{color_col}' para segmentación no se encontró en los datos. El gráfico no se segmentará.")
                        color_col = None # Ignorar la columna si no existe

                    # --- Agregación y ordenamiento para gráficos de línea/barras ---
                    # Esto es crucial para que los gráficos de evolución se vean bien
                    group_cols = [x_col]
                    if color_col:
                        group_cols.append(color_col)

                    # Para agrupar correctamente por fecha (ej. por día, por mes, etc.)
                    # Creamos una columna temporal para la agrupación si el eje X es 'Fecha'
                    if x_col == "Fecha":
                        # Agrupar por el período que tenga sentido, por ejemplo, por mes si los datos son diarios
                        # o por día si se quiere más granularidad. Aquí agrupamos por mes para una evolución más suave.
                        aggregated_df = filtered_df.copy()
                        aggregated_df['Fecha_Agrupada'] = aggregated_df['Fecha'].dt.to_period('M').dt.to_timestamp()
                        group_cols_for_agg = ['Fecha_Agrupada']
                        if color_col:
                            group_cols_for_agg.append(color_col)
                        
                        aggregated_df = aggregated_df.groupby(group_cols_for_agg)[y_col].sum().reset_index()
                        aggregated_df = aggregated_df.sort_values(by='Fecha_Agrupada')
                        x_col_for_plot = 'Fecha_Agrupada'
                    else:
                        # Para otras columnas que no son fecha, simplemente agrupar por ellas
                        aggregated_df = filtered_df.groupby(group_cols)[y_col].sum().reset_index()
                        aggregated_df = aggregated_df.sort_values(by=x_col) # Ordenar por la columna X
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
                        # Para gráficos de pastel, no se usa x_col_for_plot, sino x_col original como names
                        # y se agrupa por x_col y se suma y_col
                        # No se agrega color_col directamente en pie, se usa names y values
                        grouped_pie_df = filtered_df.groupby(x_col)[y_col].sum().reset_index()
                        fig = px.pie(grouped_pie_df, names=x_col, values=y_col,
                                     title=f"Proporción de {y_col} por {x_col}")
                    elif chart_data["chart_type"] == "scatter":
                        # Scatter plots a menudo no necesitan agregación si se quiere ver cada punto de dato
                        fig = px.scatter(filtered_df, x=x_col, y=y_col, color=color_col,
                                         title=f"Relación entre {x_col} y {y_col}",
                                         labels={x_col: x_col, y_col: y_col})

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


