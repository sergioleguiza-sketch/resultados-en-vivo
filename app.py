import streamlit as st
import pandas as pd
from supabase import create_client
from st_autorefresh import st_autorefresh

# 1. Configuración y Conexión
st.set_page_config(layout="wide", page_title="Cronoer - Resultados en Vivo")

url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# Autorefresh cada 30 segundos
st_autorefresh(interval=30 * 1000, key="datarefresh")

# 2. Funciones Lógicas
def obtener_evento_activo():
    res = supabase.table("eventos").select("*").eq("estado", "en_vivo").maybe_single().execute()
    return res.data

def obtener_ranking_espejo(id_evento):
    query = "dorsal, nro_vuelta, hora_llegada, estado, inscripciones(atletas(nombre, apellido, nacionalidad))"
    res = supabase.table("vueltas_vivo").select(query).eq("id_evento", id_evento).execute()
    
    if not res.data:
        return pd.DataFrame()
    
    df = pd.DataFrame(res.data)
    # Aplanamos el JSON de los atletas
    df['Atleta'] = df['inscripciones'].apply(lambda x: f"{x['atletas']['nombre']} {x['atletas']['apellido']}")
    df['Pais'] = df['inscripciones'].apply(lambda x: x['atletas']['nacionalidad'])
    
    # Nos quedamos con el último estado de cada corredor
    df_actual = df.sort_values('hora_llegada').groupby('dorsal').last().reset_index()
    
    # Bloque ACTIVOS: Orden por llegada (más reciente arriba)
    activos = df_actual[df_actual['estado'] == 'ACT'].sort_values('hora_llegada', ascending=False)
    
    # Bloque DNF/WINNER: Por vueltas (desc) y tiempo (asc)
    finalizados = df_actual[df_actual['estado'] != 'ACT'].sort_values(['nro_vuelta', 'hora_llegada'], ascending=[False, True])
    
    return pd.concat([activos, finalizados])

# 3. Renderizado de la Interfaz
evento = obtener_evento_activo()

if evento:
    # Header con Clima (Cronoer Style)
    st.title(f"🏆 {evento['nombre']}")
    st.write(f"### 📍 {evento['lugar']} | 🌡️ {evento.get('temperatura', '--')}°C | 💧 {evento.get('humedad', '--')}%")
    st.caption(f"Clima: {evento.get('clima_desc', 'Sin datos')}")
    st.markdown("---")

    ranking = obtener_ranking_espejo(evento['id_evento'])

    if not ranking.empty:
        # Columna de KM calculada en el momento
        ranking['KM'] = (ranking['nro_vuelta'] * 6.706).round(2)
        
        # Aplicamos el estilo de colores
        def color_filas(row):
            if row.estado == 'ACT': return ['background-color: rgba(46, 204, 113, 0.1)'] * len(row)
            if row.estado == 'WINNER': return ['background-color: #f1c40f; color: black'] * len(row)
            return ['color: #95a5a6'] * len(row)

        st.dataframe(
            ranking.style.apply(color_filas, axis=1),
            column_config={
                "dorsal": "Bib",
                "nro_vuelta": "Vueltas",
                "hora_llegada": st.column_config.DatetimeColumn("Último Cruce", format="HH:mm:ss"),
                "estado": "Estado"
            },
            hide_index=True, use_container_width=True
        )
    else:
        st.info("Carrera iniciada. Esperando el primer paso por el patio...")
else:
    st.warning("No hay eventos en vivo en este momento.")
    st.info("Próximo evento: Yaguarundí Backyard Ultra - 12 de Septiembre")

st.markdown("---")
st.caption("Sistema de Cronometraje Cronoer - Empatía con el atleta.")
