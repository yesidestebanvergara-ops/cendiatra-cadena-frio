import io
import math
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# -----------------------------------------------------------------------------
# CONFIGURACIÓN INICIAL DE LA PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Cendiatra - Monitoreo de Cadena de Frío",
    page_icon="❄️",
    layout="wide",
)

st.title("❄️ Cendiatra - Monitoreo de Cadena de Frío")
st.markdown(
    "Visualización en tiempo real, alertas de desvío e historial por"
    " sedes/equipos."
)

# -----------------------------------------------------------------------------
# CÁLCULO TÉCNICO: TEMPERATURA MEDIA CINÉTICA (MKT)
# -----------------------------------------------------------------------------
def calcular_mkt(temperaturas_celsius):
    """Calcula la Temperatura Media Cinética (MKT) en °C según la ecuación de Haynes."""
    temps_validas = [t for t in temperaturas_celsius if not pd.isna(t)]
    if not temps_validas:
        return 0.0

    delta_H = 83.144  # kJ/mol
    R = 0.0083144  # kJ/(mol*K)

    suma_exp = sum(
        math.exp(-delta_H / (R * (t + 273.15))) for t in temps_validas
    )
    promedio_exp = suma_exp / len(temps_validas)

    if promedio_exp == 0:
        return 0.0

    mkt_kelvin = (-delta_H / R) / math.log(promedio_exp)
    return mkt_kelvin - 273.15


# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE SEDES Y ENLACES (BARRA LATERAL)
# -----------------------------------------------------------------------------
st.sidebar.header("⚙️ Configuración de Sedes")

sedes_links = {
    "Refrigerador Bello": (
        "https://docs.google.com/spreadsheets/d/1XY-XqIZQZPgeLhPWtmJ6XsQJKtHp6D0S9dqOaIsiSH0/edit?usp=sharing"
    ),
    "Sede Norte": "",
    "Sede Occidente": "",
}

sede_seleccionada = st.sidebar.selectbox(
    "Seleccionar Sede / Equipo:", list(sedes_links.keys())
)
url_input = st.sidebar.text_input(
    "Enlace de Google Sheets:", value=sedes_links[sede_seleccionada]
)

st.sidebar.subheader("🌡️ Límites de Temperatura (°C)")
temp_min_permitida = st.sidebar.number_input(
    "Temp. Mínima Permitida", value=2.0, step=0.5
)
temp_max_permitida = st.sidebar.number_input(
    "Temp. Máxima Permitida", value=8.0, step=0.5
)

# Botón de recarga manual
st.sidebar.markdown("---")
if st.sidebar.button("🔄 Actualizar datos ahora", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# -----------------------------------------------------------------------------
# GENERACIÓN DEL REPORTE PDF COMPLETO
# -----------------------------------------------------------------------------
def generar_pdf_reporte(
    df,
    col_fecha,
    col_temp,
    fig,
    sede,
    periodo,
    t_min,
    t_max,
    mkt_val,
    novedades_list,
):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    story = []
    styles = getSampleStyleSheet()

    titulo_style = ParagraphStyle(
        "TituloPDF",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        textColor=colors.HexColor("#003366"),
        spaceAfter=4,
    )
    subtitulo_style = ParagraphStyle(
        "SubtituloPDF",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.gray,
        spaceAfter=12,
    )
    sec_style = ParagraphStyle(
        "SecPDF",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=colors.HexColor("#003366"),
        spaceAfter=6,
    )

    story.append(
        Paragraph("CENDIATRA - Reporte Monitoreo Cadena de Frío", titulo_style)
    )
    story.append(
        Paragraph(
            f"<b>Sede/Equipo:</b> {sede} &nbsp;&nbsp;|&nbsp;&nbsp;"
            f" <b>Período:</b> {periodo}",
            subtitulo_style,
        )
    )

    t_max_val = df[col_temp].max()
    t_min_val = df[col_temp].min()
    t_prom_val = df[col_temp].mean()
    t_actual_val = df[col_temp].iloc[-1]

    resumen_data = [
        ["Métrica", "Valor Registrado", "Rango Permitido"],
        ["Temp. Actual", f"{t_actual_val:.2f} °C", f"{t_min} °C - {t_max} °C"],
        ["Temp. Máxima", f"{t_max_val:.2f} °C", f"{t_min} °C - {t_max} °C"],
        ["Temp. Mínima", f"{t_min_val:.2f} °C", f"{t_min} °C - {t_max} °C"],
        ["Temp. Promedio", f"{t_prom_val:.2f} °C", f"{t_min} °C - {t_max} °C"],
        [
            "Temp. Media Cinética (MKT)",
            f"{mkt_val:.2f} °C",
            f"{t_min} °C - {t_max} °C",
        ],
    ]
    tabla_resumen = Table(resumen_data, colWidths=[180, 170, 170])
    tabla_resumen.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -1),
                [colors.white, colors.HexColor("#F2F5F8")],
            ),
        ])
    )
    story.append(tabla_resumen)
    story.append(Spacer(1, 10))

    try:
        img_bytes = fig.to_image(format="png", width=750, height=320, scale=2)
        img_pdf = Image(io.BytesIO(img_bytes), width=520, height=220)
        story.append(img_pdf)
    except Exception as e:
        story.append(
            Paragraph(f"<i>(Gráfico no disponible: {e})</i>", styles["Normal"])
        )

    story.append(Spacer(1, 10))

    # Novedades y Acciones Correctivas en el PDF
    if novedades_list:
        story.append(
            Paragraph(
                "Bitácora de Novedades / Acciones Correctivas:", sec_style
            )
        )
        nov_data = [["Fecha y Hora", "Sede", "Observación / Causa"]]
        for item in novedades_list:
            nov_data.append(
                [item["fecha"], item["sede"], item["observaciones"]]
            )

        tabla_nov = Table(nov_data, colWidths=[120, 100, 300])
        tabla_nov.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4A607A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ])
        )
        story.append(tabla_nov)

    doc.build(story)
    buffer.seek(0)
    return buffer


# -----------------------------------------------------------------------------
# CARGA Y PROCESAMIENTO DE DATOS
# -----------------------------------------------------------------------------
@st.cache_data(ttl=30)
def cargar_datos_sheets(url):
    if not url:
        return None, None, None

    if "docs.google.com/spreadsheets" in url:
        sheet_id = url.split("/d/")[1].split("/")[0]
        url_csv = (
            f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv"
        )
    else:
        url_csv = url

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
    }
    response = requests.get(url_csv, headers=headers, timeout=10)

    if response.status_code != 200:
        raise Exception(
            f"Error HTTP {response.status_code}. Revisa permisos del archivo."
        )

    df = pd.read_csv(io.StringIO(response.text), dtype=str)
    df.columns = [str(col).strip() for col in df.columns]

    col_fecha = df.columns[0]
    col_temp = df.columns[1]

    df[col_temp] = df[col_temp].str.replace(",", ".").astype(float)
    df[col_fecha] = pd.to_datetime(
        df[col_fecha], dayfirst=True, errors="coerce"
    )
    df = df.dropna(subset=[col_fecha, col_temp]).sort_values(by=col_fecha)

    return df, col_fecha, col_temp


# Inicializar estado para bitácora de novedades
if "bitacora" not in st.session_state:
    st.session_state.bitacora = []

# -----------------------------------------------------------------------------
# DASHBOARD PRINCIPAL
# -----------------------------------------------------------------------------
if url_input:
    try:
        df_raw, col_fecha, col_temp = cargar_datos_sheets(url_input)

        if df_raw is not None and not df_raw.empty:
            st.sidebar.markdown("---")
            st.sidebar.header("📅 Filtros de Período")
            opcion_filtro = st.sidebar.radio(
                "Filtrar datos por:",
                ["General", "Por Año", "Por Mes", "Por Día"],
            )

            df = df_raw.copy()

            if opcion_filtro == "Por Año":
                anios = sorted(df[col_fecha].dt.year.unique(), reverse=True)
                anio_sel = st.sidebar.selectbox("Selecciona el Año:", anios)
                df = df[df[col_fecha].dt.year == anio_sel]

            elif opcion_filtro == "Por Mes":
                df["AnioMes"] = df[col_fecha].dt.strftime("%Y-%m")
                meses = sorted(df["AnioMes"].unique(), reverse=True)
                mes_sel = st.sidebar.selectbox(
                    "Selecciona el Mes (Año-Mes):", meses
                )
                df = df[df["AnioMes"] == mes_sel]

            elif opcion_filtro == "Por Día":
                dias = sorted(df[col_fecha].dt.date.unique(), reverse=True)
                dia_sel = st.sidebar.date_input(
                    "Selecciona el Día:", value=dias[0]
                )
                df = df[df[col_fecha].dt.date == dia_sel]

            if df.empty:
                st.warning(
                    "No hay registros disponibles para el período"
                    " seleccionado."
                )
            else:
                temp_actual = df[col_temp].iloc[-1]
                fecha_ultima = df[col_fecha].iloc[-1].strftime(
                    "%d/%m/%Y %H:%M"
                )
                temp_max = df[col_temp].max()
                temp_min = df[col_temp].min()
                temp_prom = df[col_temp].mean()
                mkt_val = calcular_mkt(df[col_temp].tolist())

                # Indicador de Alerta de Desvío Activo
                if (
                    temp_actual > temp_max_permitida
                    or temp_actual < temp_min_permitida
                ):
                    st.error(
                        f"⚠️ **DESVÍO TÉRMICO DETECTADO**: La temperatura actual"
                        f" ({temp_actual:.2f} °C) se encuentra fuera del rango"
                        f" permitido ({temp_min_permitida}°C -"
                        f" {temp_max_permitida}°C)."
                    )

                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric(
                    "🌡️ Temp. Actual",
                    f"{temp_actual:.2f} °C",
                    help=f"Última lectura: {fecha_ultima}",
                )
                c2.metric("🔥 Temp. Máxima", f"{temp_max:.2f} °C")
                c3.metric("❄️ Temp. Mínima", f"{temp_min:.2f} °C")
                c4.metric("📈 Temp. Promedio", f"{temp_prom:.2f} °C")
                c5.metric(
                    "🧪 Temp. MKT",
                    f"{mkt_val:.2f} °C",
                    help="Temperatura Media Cinética (Haynes)",
                )

                st.markdown("---")

                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=df[col_fecha],
                        y=df[col_temp],
                        mode="lines",
                        name="Temperatura (°C)",
                        line=dict(color="#0066CC", width=1.5),
                    )
                )
                fig.add_hline(
                    y=temp_max_permitida,
                    line_dash="dash",
                    line_color="red",
                    annotation_text=f"Límite Máx ({temp_max_permitida}°C)",
                )
                fig.add_hline(
                    y=temp_min_permitida,
                    line_dash="dash",
                    line_color="blue",
                    annotation_text=f"Límite Mín ({temp_min_permitida}°C)",
                )

                fig.update_layout(
                    title=f"Cendiatra - {sede_seleccionada} ({opcion_filtro})",
                    xaxis_title="Fecha y Hora",
                    yaxis_title="Temperatura (°C)",
                    hovermode="x unified",
                    template="plotly_white",
                    height=420,
                )

                st.plotly_chart(fig, use_container_width=True)

                # Registro de Acciones Correctivas
                st.markdown(
                    "### 📝 Registro de Novedades y Acciones Correctivas"
                )
                with st.expander("➕ Registrar nueva observación / novedad"):
                    with st.form("form_novedad"):
                        obs_texto = st.text_area(
                            "Descripción de la novedad o acción correctiva:"
                        )
                        btn_guardar = st.form_submit_button("Guardar Registro")
                        if btn_guardar and obs_texto.strip():
                            st.session_state.bitacora.append({
                                "fecha": datetime.now().strftime(
                                    "%d/%m/%Y %H:%M"
                                ),
                                "sede": sede_seleccionada,
                                "observaciones": obs_texto.strip(),
                            })
                            st.success(
                                "Novedad registrada y adjuntada al reporte PDF."
                            )

                st.markdown("### 🖨️ Exportar Informes")
                col_exp1, col_exp2 = st.columns(2)

                pdf_buffer = generar_pdf_reporte(
                    df=df,
                    col_fecha=col_fecha,
                    col_temp=col_temp,
                    fig=fig,
                    sede=sede_seleccionada,
                    periodo=opcion_filtro,
                    t_min=temp_min_permitida,
                    t_max=temp_max_permitida,
                    mkt_val=mkt_val,
                    novedades_list=st.session_state.bitacora,
                )

                # Exportar PDF
                col_exp1.download_button(
                    label="📄 Descargar Informe PDF",
                    data=pdf_buffer,
                    file_name=f"Reporte_Cadena_Frio_{sede_seleccionada}_{opcion_filtro}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )

                # Exportar datos a Excel (.csv)
                csv_data = df[[col_fecha, col_temp]].to_csv(index=False)
                col_exp2.download_button(
                    label="📊 Descargar Datos Filtrados (CSV/Excel)",
                    data=csv_data,
                    file_name=f"Datos_{sede_seleccionada}_{opcion_filtro}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

                with st.expander("📄 Ver tabla de registros filtrados"):
                    st.dataframe(
                        df[[col_fecha, col_temp]], use_container_width=True
                    )

        else:
            st.warning("El archivo no contiene registros válidos.")

    except Exception as e:
        st.error(f"Error al procesar los datos: {e}")
else:
    st.info("Ingresa un enlace de Google Sheets en el panel izquierdo.")
