import streamlit as st
import pandas as pd
from supabase import create_client
from st_autorefresh import st_autorefresh

# 1. Configuración de página (Ancho completo para el Grid)
st.set_page_config(layout="wide", page_title="Backyard Ultra AR - Resultados en Vivo")

# 2. Conexión a la "Fuente de la Verdad" (Tus credenciales de Supabase)
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# 3. Autorefresh cada 30 segundos (Mantiene el "Vivo" sin intervención del usuario)
st_autorefresh(interval=30 * 1000, key="datarefresh")

# --- CABECERA ESTILO BELGA ---
st.title("🏆 Resultados en Vivo: Yaguarundí- 2026")
st.markdown("---")

# 1. Definir la función para traer el evento
def obtener_evento_activo():
    res = supabase.table("eventos").select("*").eq("estado", "en_vivo").maybe_single().execute()
    return res.data

# 2. Ejecutar la función para tener los datos del clima
evento = obtener_evento_activo()

# 3. RECIÉN ACÁ usar la variable 'evento' para el header
if evento:
    st.write(f"### 🌡️ {evento['temperatura']}°C | 💧 {evento['humedad']}% | {evento['clima_desc']}")
    id_evento_actual = evento['id_evento']
else:
    st.warning("No hay eventos activos en este momento.")
    st.stop() # Frena la ejecución si no hay evento

# --- EL GRID DE RESULTADOS ---
ranking_final = obtener_datos_publicos(id_evento_actual)

def colorear_ranking(row):
    if row.estado == "ACT":
        return ['background-color: rgba(46, 204, 113, 0.1)'] * len(row) # Verde muy tenue
    if row.estado == "WINNER":
        return ['background-color: #f1c40f; color: black; font-weight: bold'] * len(row)
    return ['color: #95a5a6; opacity: 0.7'] * len(row) # Gris para DNF

st.dataframe(
    ranking_final.style.apply(colorear_ranking, axis=1),
    column_config={
        "nro_vuelta": "Vueltas",
        "hora_llegada": st.column_config.DatetimeColumn("Último Arribo", format="HH:mm:ss"),
        "estado": "Situación"
    },
    hide_index=True,
    use_container_width=True
)
def obtener_datos_publicos(id_evento):
    # Traemos las vueltas, inscripciones y el país (clave para la Bitácora)
    query = """
        dorsal, nro_vuelta, hora_llegada, estado,
        inscripciones(atletas(nombre, apellido, nacionalidad))
    """
    res = supabase.table("vueltas_vivo").select(query).eq("id_evento", id_evento).execute()
    df = pd.DataFrame(res.data)

    if df.empty:
        return df

    # Nos quedamos con el último registro de cada dorsal (el estado más actual)
    # Ordenamos por hora de llegada para asegurar que el 'last' sea el más reciente
    df_actual = df.sort_values('hora_llegada').groupby('dorsal').last().reset_index()

    # --- SEPARACIÓN DE BLOQUES ---
    activos = df_actual[df_actual['estado'] == 'ACT'].copy()
    no_activos = df_actual[df_actual['estado'] != 'ACT'].copy()

    # 1. ORDEN ACTIVOS: Por hora de llegada (el que llegó recién, arriba)
    activos = activos.sort_values(by='hora_llegada', ascending=False)

    # 2. ORDEN DNF: Por vueltas completadas (desc) y luego por tiempo (asc)
    no_activos = no_activos.sort_values(by=['nro_vuelta', 'hora_llegada'], ascending=[False, True])

    # Unimos ambos bloques: Activos primero, DNF después
    return pd.concat([activos, no_activos])

def cargar_ranking():
    # Consulta encapsulada: Traemos datos de Vueltas + Inscripciones + Atletas
    # Nota: Usamos la relación que definimos en el esquema SQL
    query = """
        dorsal, 
        nro_vuelta, 
        estado, 
        inscripciones (
            asistente,
            atletas (nombre, apellido, localidad, nacionalidad)
        )
    """
    response = supabase.table("vueltas_vivo").select(query).execute()
    return response.data

def procesar_ranking(datos):
    if not datos:
        return pd.DataFrame()

    # Aplanamos el JSON de Supabase para convertirlo en tabla
    filas = []
    for reg in datos:
        atleta = reg['inscripciones']['atletas']
        filas.append({
            "Bib": reg['dorsal'],
            "Name": f"{atleta['nombre']} {atleta['apellido']}",
            "Localidad": atleta['localidad'],
            "Country": atleta['nacionalidad'],
            "Laps": reg['nro_vuelta'],
            "KM": round(reg['nro_vuelta'] * 6.706, 2),
            "Estado": reg['estado']
        })
    
    df = pd.DataFrame(filas)
    
    # Lógica de Ranking: 1ro por Laps (desc), 2do por Estado (ACT arriba)
    # Agrupamos por Bib para quedarnos con la última vuelta registrada de cada uno
    ranking = df.sort_values(['Laps', 'Bib'], ascending=[False, True]).drop_duplicates('Bib')
    return ranking

# --- RENDERIZADO DEL GRID ---
datos_frescos = cargar_ranking()
ranking_df = procesar_ranking(datos_frescos)

if not ranking_df.empty:
    # Aplicamos estilos de color (Dorado para Winner, Gris para DNF)
    def style_rows(row):
        if row.Estado == "WINNER":
            return ['background-color: #f1c40f; color: black; font-weight: bold'] * len(row)
        if "DNF" in row.Estado:
            return ['color: #95a5a6'] * len(row)
        return [''] * len(row)

    # El Grid de Resultados
    st.dataframe(
        ranking_df.style.apply(style_rows, axis=1),
        column_config={
            "Country": st.column_config.TextColumn("País"), # Aquí podrías usar banderas emoji
            "KM": st.column_config.NumberColumn(format="%.2f km"),
            "Laps": st.column_config.NumberColumn("Vueltas"),
        },
        hide_index=True,
        use_container_width=True
    )
else:
    st.info("Esperando el inicio de la Vuelta 1 para mostrar resultados...")

# Pie de página con tu impronta
st.markdown("---")
st.caption("Sistema de Cronometraje desarrollado por Cronoer.com.ar - Empatía con el atleta.")
