import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
from supabase import create_client
#from st_autorefresh import st_autorefresh

# Inyección de CSS para compactar la interfaz en móviles
st.markdown(
    """
    <style>
    /* 1. Reducir el contenedor de la métrica */
    [data-testid="stMetric"] {
        padding: 0px !important;
        text-align: center;
    }

    /* 2. Achicar el título de la métrica (la etiqueta arriba del número) */
    [data-testid="stMetricLabel"] {
        font-size: 0.8rem !important;
        margin-bottom: -10px !important;
    }

    /* 3. Achicar el número de la métrica */
    [data-testid="stMetricValue"] {
        font-size: 1.4rem !important;
    }

    /* 4. Eliminar el espacio sobrante entre bloques de métricas */
    div[data-testid="stMetric"] > div {
        margin-bottom: 0px !important;
    }

    /* 5. Acercar las columnas de métricas entre sí */
    [data-testid="column"] {
        width: fit-content !important;
        flex: 1 1 auto !important;
    }
    
    /* 6. Reducir el espacio general del bloque vertical */
    .stVerticalBlock {
        gap: 0.2rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

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
        
def calcular_tiempo_neto(fila, hora_cero_evento):
    # Forzamos a que ambos sean UTC para la resta
    if hora_cero_evento.tzinfo is None:
        hora_cero_evento = hora_cero_evento.replace(tzinfo=timezone.utc)
    else:
        hora_cero_evento = hora_cero_evento.astimezone(timezone.utc)
    
    # 2. Calculamos el inicio del patio actual
    minutos_transcurridos = (fila['nro_vuelta'] - 1) * 60
    inicio_patio = hora_cero_evento + timedelta(minutes=minutos_transcurridos)
    
    # 3. Convertimos la llegada a datetime y aseguramos UTC
    llegada = pd.to_datetime(fila['hora_llegada'])
    if llegada.tzinfo is None:
        llegada = llegada.replace(tzinfo=timezone.utc)
    else:
        llegada = llegada.astimezone(timezone.utc)
    
    # 4. Ahora sí restamos con seguridad
    duracion = llegada - inicio_patio
    
    # Formateo MM:SS
    total_segundos = int(duracion.total_seconds())
    if total_segundos < 0: return "00:00" # Por si hay algún desfase de milisegundos
    
    minutos, segundos = divmod(total_segundos, 60)
    return f"{minutos:02d}:{segundos:02d}"

def obtener_ranking_espejo(id_evento):
    query = """
        dorsal, nro_vuelta, hora_llegada, estado, segundos_netos,
        inscripciones:inscripciones!inner(
            asistente,
            atletas:dni_atleta(nombre, apellido, nacionalidad,pb)
        )
    """
    res = supabase.table("vueltas_vivo").select(query).eq("id_evento", id_evento).execute()
    
    if not res.data: return pd.DataFrame()

    lista_ranking = []
    for r in res.data:
        ins = r.get('inscripciones', {})
        atl = ins.get('atletas', {})
        fila = {
            "dorsal": r['dorsal'],
            "nro_vuelta": r['nro_vuelta'],
            "hora_llegada": r['hora_llegada'],
            "estado": r['estado'],
            "segundos_netos": r.get('segundos_netos', 0), # Agrega esta línea
            "Atleta": f"{atl.get('nombre', '')} {atl.get('apellido', '')}".strip(),
            "Pais": atl.get('nacionalidad', 'ARG'),
            "PB": atl.get('pb', '')
        }
        lista_ranking.append(fila)
    
    df = pd.DataFrame(lista_ranking)
    # Importante: Nos quedamos con el último registro de cada uno
    df_actual = df.sort_values('hora_llegada').groupby('dorsal').last().reset_index()
    
    # --- BLOQUES DE RANKING ---
    # 1. Los que están en carrera (ACT)
    activos = df_actual[df_actual['estado'] == 'ACT'].sort_values(['nro_vuelta', 'hora_llegada'], ascending=[False, True])
    
    # 2. Los que terminaron (DNF, DQ, WINNER)
    finalizados = df_actual[df_actual['estado'] != 'ACT'].sort_values(['nro_vuelta', 'hora_llegada'], ascending=[False, True])
    
    # Unimos ambos bloques: Activos siempre arriba
    return pd.concat([activos, finalizados])

# 3. Renderizado de la Interfaz
#evento = obtener_evento_activo()

# --- COLOCAR ESTO ANTES DEL "if evento:" ---

@st.fragment(run_every="30s")
def mostrar_ranking_actualizado(evento_id, hora_cero_local):
    # Traemos los datos frescos de Supabase
    ranking = obtener_ranking_espejo(evento_id)
    # 1. Determinamos si hay un ganador para cambiar la etiqueta
    # Buscamos si algún registro en el ranking tiene el estado 'WINNER'
    tiene_ganador = (ranking['estado'] == 'WINNER').any() if not ranking.empty else False
    
    # 2. Definimos el texto y el color del badge
    if tiene_ganador:
        etiqueta = "🔴 FINALIZADO"
        color_header = "gray"
    else:
        etiqueta = "🟢 EN CURSO"
        color_header = "green"
    
    # Definimos la hora de inicio del evento (asegúrate que en la base de datos esté como timestamp)
    # Si no existe el campo, usamos la hora actual como backup para que no rompa
    # Usamos 'hora_cero' que es el timestamp exacto de largada, no 'fecha_inicio'
    
    hora_cero_local = pd.to_datetime(evento.get('hora_cero', datetime.now(timezone.utc)))
    ahora = datetime.now(timezone.utc)
    tiempo_transcurrido = ahora - hora_cero_local
    segundos_totales = tiempo_transcurrido.total_seconds()
    
    # Calculamos el patio actual basado en el tiempo
    if segundos_totales < 0:
        patio_actual = 0
    else:
        patio_actual = int(segundos_totales // 3600) + 1
    
    if not ranking.empty:
        # 1. Cálculos de métricas rápidas (Activos y Patio)
        total_activos = int((ranking['estado'] == 'ACT').sum())
        hora_cero_local = pd.to_datetime(evento.get('hora_cero', datetime.now(timezone.utc)))
        ahora = datetime.now(timezone.utc)
        segundos_totales = (ahora - hora_cero_local).total_seconds()
        patio_actual = int(segundos_totales // 3600) + 1 if segundos_totales > 0 else 1

        # 2. Render de métricas compactas
        st.markdown(
            f"**Vuelta:** #{patio_actual}  |  **Activos:** {total_activos}  |  **KM:** {round(patio_actual * 6.706, 2)}", 
            unsafe_allow_html=True
        )

        # 3. Procesamiento de la tabla (Banderas, KM, Tiempos)
        ranking['KM'] = (ranking['nro_vuelta'] * 6.706).round(2)
        banderas = {"ARG": "🇦🇷 ARG", "URY": "🇺🇾 URY", "BRA": "🇧🇷 BRA", "CHL": "🇨🇱 CHL", "GER": "🇩🇪 GER", "ISR": "🇮🇱 ISR", "ESP": "🇪🇸 ESP", "USA": "🇺🇸 USA"}
        ranking['Pais'] = ranking['Pais'].map(lambda x: banderas.get(x, x))
        ranking['PB'] = pd.to_numeric(ranking['PB'], errors='coerce').astype('Int64')
        ranking["Tiempo Vuelta"] = ranking["segundos_netos"].apply(formatear_segundos)
        
        # 4. Orden lógico (Ganador > Activos > Vueltas > Tiempo)
        ranking['es_activo'] = ranking['estado'] == 'ACT'
        # Creamos una columna auxiliar para priorizar al Ganador
        ranking['es_ganador'] = ranking['estado'] == 'WINNER'
        # Ajustamos el orden: 
        # 1° Ganador (True arriba)
        # 2° Activos (True arriba)
        # 3° Mayor número de vueltas
        # 4° Menor tiempo de llegada (más rápido)
        ranking = ranking.sort_values(by=["es_ganador", "es_activo", "nro_vuelta", "hora_llegada"], ascending=[False, False, False, True])

        # Aplicamos el estilo de colores
        def color_filas(row):
            # Verde esmeralda suave (Cronoer Style)
            if row.estado == 'ACT': 
                return ['background-color: rgba(76, 175, 80, 0.25); color: black'] * len(row)
            # Dorado para el ganador
            if row.estado == 'WINNER': 
                return ['background-color: #f1c40f; color: black; font-weight: bold'] * len(row)
            # Gris para DNF
            return ['color: #95a5a6; font-style: italic'] * len(row)
        # 5. Mostrar la grilla
        columnas_visibles = ["dorsal", "Atleta", "Pais", "nro_vuelta", "estado", "KM", "Tiempo Vuelta", "PB"]

        def formatear_segundos(s):
            if pd.isna(s) or s <= 0:
                return "00:00"
            m, s = divmod(int(s), 60)
            return f"{m:02d}:{s:02d}"
        
        # Aplicamos el formato a la columna del ranking
        ranking["Tiempo Vuelta"] = ranking["segundos_netos"].apply(formatear_segundos)
        st.dataframe(
            ranking[columnas_visibles].style.apply(color_filas, axis=1),
            column_config={
                "dorsal": "Bib",
                "KM": st.column_config.NumberColumn("KM", format="%.2f"),
                "Tiempo Vuelta": st.column_config.TextColumn("Última Vuelta"),
                "PB": st.column_config.NumberColumn("PB", format="%i")
            },
            hide_index=True, 
            use_container_width=True
        )
    else:
        st.info("Esperando el primer paso por el patio...")

if evento:
    ranking = obtener_ranking_espejo(evento['id_evento'])
    
    # Header con Clima (Cronoer Style)
    st.title(f"🏆 {evento['nombre']}")
    st.subheader(f":{color_header}[{etiqueta}]") # Esto pone el texto en color
    st.write(f"### 📍 {evento['lugar']}")
    st.write(f"### 🌡️ {evento.get('temperatura', '--')}°C | 💧 {evento.get('humedad', '--')}%")

    st.caption(f"Clima: {evento.get('clima_desc', 'Sin datos')}")
    st.markdown("---")
    
    hora_cero_local = pd.to_datetime(evento.get('hora_cero', datetime.now(timezone.utc)))
    
    # LLAMADA AL FRAGMENTO: Esto es lo que se refresca cada 30s
    mostrar_ranking_actualizado(evento['id_evento'], hora_cero_local)

else:
    st.warning("No hay eventos en vivo en este momento.")
    st.info("Próximo evento: Yaguarundí Backyard Ultra - 12 de Septiembre")

st.markdown("---")
st.caption("Sistema de Cronometraje CRONOER - Empatía con el atleta.")
