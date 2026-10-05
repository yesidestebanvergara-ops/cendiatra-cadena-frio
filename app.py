import io
import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle

# -----------------------------------------------------------------------------
# CONFIGURACIÓN INICIAL DE LA PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Cendiatra - Monitoreo de Cadena de Frío",
    page_icon="❄️",
    layout="wide",
)

st.title("❄️ Cendiatra - Monitoreo de Cadena de Frío")
st.markdown("Visualización en tiempo real e historial de temperatura por sedes/equipos.")

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE SEDES Y ENLACES (BARRA LATERAL)
# -----------------------------------------------------------------------------
st.sidebar.header("⚙️ Configuración de Sedes")

sedes_links = {
    "Refrigerador Bello": "https://docs.google.com/spreadsheets/d/1XY-XqIZQZPgeLhPWtmJ6XsQJKtHp6D0S9dqOaIsiSH0/edit?usp=sharing",
    "Sede Norte (Ejemplo)": "",
    "Sede Sur (Ejemplo)": "",
}

sede_seleccionada = st.sidebar.selectbox("Seleccionar Sede / Equipo:", list(sedes_links.keys()))
url_input = st.sidebar.text_input("Enlace de Google Sheets:", value=sedes_links[sede_seleccionada])

st.sidebar.subheader("🌡️ Límites de Temperatura (°C)")
temp_min_permitida = st.sidebar.number_input("Temp. Mínima Permitida", value=2.0, step=0.5)
temp_max_permitida = st.sidebar.number_input("Temp. Máxima Permitida", value=8.0, step=0.5)

# -----------------------------------------------------------------------------
# GENERACIÓN DEL REPORTE PDF (SIN FIRMAS, CON GRÁFICO)
# -----------------------------------------------------------------------------
def generar_pdf_reporte(df, col_fecha, col_temp, fig, sede, periodo, t_min, t_max):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    styles = getSampleStyleSheet()

    titulo_style = ParagraphStyle(
        'TituloPDF',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#003366'),
        spaceAfter=6
    )
    subtitulo_style = ParagraphStyle(
        'SubtituloPDF',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.gray,
        spaceAfter=15
    )

    story.append(Paragraph("CENDIATRA - Reporte Monitoreo Cadena de Frío", titulo_style))
    story.append(Paragraph(f"<b>Sede/Equipo:</b> {sede} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Período:</b> {periodo}", subtitulo_style))
    story.append(Spacer(1, 5))

    t_max_val = df[col_temp].max()
    t_min_val = df[col_temp].min()
    t_prom_val = df[col_temp].mean()
    t_actual_val = df[col_temp].iloc[-1]

    resumen_data = [
        ["Métrica", "Valor Actual / Estadísticas", "Rango Permitido"],
        ["Temp. Actual", f"{t_actual_val:.2f} °C", f"{t_min} °C - {t_max} °C"],
        ["Temp. Máxima", f"{t_max_val:.2f} °C", f"{t_min} °C - {t_max} °C"],
        ["Temp. Mínima", f"{t_min_val:.2f} °C", f"{t_min} °C - {t_max} °C"],
        ["Temp. Promedio", f"{t_prom_val:.2f} °C", f"{t_min} °C - {t_max} °C"]
    ]
    tabla_resumen = Table(resumen_data, colWidths=[160, 180, 180])
    tabla_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F2F5F8')])
    ]))
    story.append(tabla_resumen)
    story.append(Spacer(1, 15))

    try:
        img_bytes = fig.to_image(format="png", width=750, height=350, scale=2)
        img_buffer = io.BytesIO(img_bytes)
        img_pdf = Image(img_buffer, width=540, height=250)
        story.append(img_pdf)
    except Exception as e:
        story.append(Paragraph(f"<i>(No se pudo renderizar el gráfico en PDF: {e})</i>", styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    return buffer

# -----------------------------------------------------------------------------
# CARGA Y PROCESAMIENTO DE DATOS EN TIEMPO REAL
# -----------------------------------------------------------------------------
@st.cache_data(ttl=30)
def cargar_datos_sheets(url):
    if not url:
        return None, None, None

    if "docs.google.com/spreadsheets" in url:
        sheet_id = url.split("/d/")[1].split("/")[0]
        url_csv = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv"
    else:
        url_csv = url

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    response = requests.get(url_csv, headers=headers, timeout=10)

    if response.status_code != 200:
        raise Exception(f"Error HTTP {response.status_code}. Revisa los permisos del archivo.")

    df = pd.read_csv(io.StringIO(response.text), dtype=str)
    df.columns = [str(col).strip() for col in df.columns]

    col_fecha = df.columns[0]
    col_temp = df.columns[1]

    df[col_temp] = df[col_temp].str.replace(",", ".").astype(float)
    df[col_fecha] = pd.to_datetime(df[col_fecha], dayfirst=True, errors="coerce")
    df = df.dropna(subset=[col_fecha, col_temp]).sort_values(by=col_fecha)

    return df, col_fecha, col_temp

# -----------------------------------------------------------------------------
# DASHBOARD PRINCIPAL
# -----------------------------------------------------------------------------
if url_input:
    try:
        df_raw, col_fecha, col_temp = cargar_datos_sheets(url_input)

        if df_raw is not None and not df_raw.empty:
            st.sidebar.markdown("---")
            st.sidebar.header("📅 Filtros de Período")

            opcion_filtro = st.sidebar.radio("Filtrar datos por:", ["General", "Por Año", "Por Mes", "Por Día"])

            df = df_raw.copy()

            if opcion_filtro == "Por Año":
                anios = sorted(df[col_fecha].dt.year.unique(), reverse=True)
                anio_sel = st.sidebar.selectbox("Selecciona el Año:", anios)
                df = df[df[col_fecha].dt.year == anio_sel]

            elif opcion_filtro == "Por Mes":
                df["AnioMes"] = df[col_fecha].dt.strftime("%Y-%m")
                meses = sorted(df["AnioMes"].unique(), reverse=True)
                mes_sel = st.sidebar.selectbox("Selecciona el Mes (Año-Mes):", meses)
                df = df[df["AnioMes"] == mes_sel]

            elif opcion_filtro == "Por Día":
                dias = sorted(df[col_fecha].dt.date.unique(), reverse=True)
                dia_sel = st.sidebar.date_input("Selecciona el Día:", value=dias[0])
                df = df[df[col_fecha].dt.date == dia_sel]

            if df.empty:
                st.warning("No hay registros disponibles para el período seleccionado.")
            else:
                temp_actual = df[col_temp].iloc[-1]
                fecha_ultima = df[col_fecha].iloc[-1].strftime("%d/%m/%Y %H:%M")
                temp_max = df[col_temp].max()
                temp_min = df[col_temp].min()
                temp_prom = df[col_temp].mean()

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("🌡️ Temp. Actual", f"{temp_actual:.2f} °C", help=f"Última lectura: {fecha_ultima}")
                c2.metric("🔥 Temp. Máxima", f"{temp_max:.2f} °C")
                c3.metric("❄️ Temp. Mínima", f"{temp_min:.2f} °C")
                c4.metric("📈 Temp. Promedio", f"{temp_prom:.2f} °C")

                st.markdown("---")

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df[col_fecha],
                    y=df[col_temp],
                    mode="lines",
                    name="Temperatura (°C)",
                    line=dict(color="#0066CC", width=1.5)
                ))
                fig.add_hline(y=temp_max_permitida, line_dash="dash", line_color="red", annotation_text=f"Límite Máx ({temp_max_permitida}°C)")
                fig.add_hline(y=temp_min_permitida, line_dash="dash", line_color="blue", annotation_text=f"Límite Mín ({temp_min_permitida}°C)")

                fig.update_layout(
                    title=f"Cendiatra - {sede_seleccionada} ({opcion_filtro})",
                    xaxis_title="Fecha y Hora",
                    yaxis_title="Temperatura (°C)",
                    hovermode="x unified",
                    template="plotly_white",
                    height=450
                )

                st.plotly_chart(fig, use_container_width=True)

                st.markdown("### 🖨️ Exportar e Imprimir Informe PDF")
                
                pdf_buffer = generar_pdf_reporte(
                    df=df,
                    col_fecha=col_fecha,
                    col_temp=col_temp,
                    fig=fig,
                    sede=sede_seleccionada,
                    periodo=opcion_filtro,
                    t_min=temp_min_permitida,
                    t_max=temp_max_permitida
                )

                st.download_button(
                    label="📄 Descargar Informe PDF con Gráfico (Listo para Imprimir)",
                    data=pdf_buffer,
                    file_name=f"Reporte_Cadena_Frio_{sede_seleccionada}_{opcion_filtro}.pdf",
                    mime="application/pdf"
                )

                with st.expander("📄 Ver registros filtrados"):
                    st.dataframe(df[[col_fecha, col_temp]], use_container_width=True)

        else:
            st.warning("El archivo no contiene registros válidos.")

    except Exception as e:
        st.error(f"Error al procesar los datos: {e}")
else:
    st.info("Ingresa un enlace de Google Sheets en el panel izquierdo.")
