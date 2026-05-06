import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
from supabase import create_client
#from st_autorefresh import st_autorefresh

# 1. Configuración y Conexión
st.set_page_config(layout="wide", page_title="BACKYARD ULTRA.ar - Resultados en Vivo")

url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# Autorefresh cada 30 segundos
#st_autorefresh(interval=30 * 1000, key="datarefresh")

# 2. Funciones Lógicas
# --- REEMPLAZO EN EL RENDERIZADO ---

# 1. Traemos TODOS los eventos que estén "en_vivo" (pueden ser varios)
res_eventos = supabase.table("eventos").select("*").eq("estado", "en_vivo").execute()
eventos_lista = res_eventos.data

if eventos_lista:
    # 2. Si hay más de uno, mostramos el selector
    if len(eventos_lista) > 1:
        nombres_eventos = [e['nombre'] for e in eventos_lista]
        seleccion = st.selectbox("📍 Seleccioná la carrera en curso:", nombres_eventos)
        
        # Filtramos para quedarnos con los datos del evento elegido
        evento = next(e for e in eventos_lista if e['nombre'] == seleccion)
    else:
        # Si hay uno solo, lo asignamos directo
        evento = eventos_lista[0]

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
    activos = df_actual[df_actual['estado'] == 'ACT'].sort_values(['nro_vuelta', 'hora_llegada'], ascending=[False, True])
    
    # Bloque DNF/WINNER: Por vueltas (desc) y tiempo (asc)
    finalizados = df_actual[df_actual['estado'] != 'ACT'].sort_values(['nro_vuelta', 'hora_llegada'], ascending=[False, True])
    
    return pd.concat([activos, finalizados])

# 3. Renderizado de la Interfaz
#evento = obtener_evento_activo()

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

        # 2. AQUÍ VA EL CÓDIGO DE FORMATO DE HORA
        # Esto transforma "2026-05-05T22:51:00Z" en "22:51:00"
        ranking['hora_llegada'] = pd.to_datetime(ranking['hora_llegada']).dt.strftime('%H:%M:%S')
        
        # Aplicamos el estilo de colores
        def color_filas(row):
            if row.estado == 'ACT': return ['background-color: rgba(46, 204, 113, 0.1)'] * len(row)
            if row.estado == 'WINNER': return ['background-color: #f1c40f; color: black'] * len(row)
            return ['color: #95a5a6'] * len(row)

        # Definimos el orden de las columnas que queremos mostrar
        columnas_visibles = ["dorsal", "Atleta", "Pais", "nro_vuelta", "KM", "hora_llegada", "estado"]

        st.dataframe(
            ranking[columnas_visibles].style.apply(color_filas, axis=1), # Solo mostramos las visibles
            column_config={
                "dorsal": "Bib",
                "Atleta": "Atleta",
                "Pais": "País",
                "nro_vuelta": "Vueltas",
                "KM": st.column_config.NumberColumn("KM", format="%.2f"), # Redondeamos los decimales
                "hora_llegada": st.column_config.DatetimeColumn("Última Vuelta", format="HH:mm:ss"),
                "estado": "Estado"
            },
            hide_index=True, 
            use_container_width=True
        )
    else:
        st.info("Carrera iniciada. Esperando el primer paso por el patio...")
else:
    st.warning("No hay eventos en vivo en este momento.")
    st.info("Próximo evento: Yaguarundí Backyard Ultra - 12 de Septiembre")

st.markdown("---")
st.caption("Sistema de Cronometraje CRONOER - Empatía con el atleta.")
