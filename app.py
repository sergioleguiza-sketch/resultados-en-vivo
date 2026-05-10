import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
from supabase import create_client
#from st_autorefresh import st_autorefresh

# Inyección de CSS para compactar la interfaz en móviles
st.markdown(
    """
    <style>
    /* 1. Reducir el espacio superior (Padding del contenedor principal) */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    
    /* 2. Compactar el espacio entre elementos (títulos, métricas, markdown) */
    div[data-testid="stVerticalBlock"] > div {
        gap: 0.5rem !important;
    }

    /* 3. Ajustar el tamaño del título para que no ocupe media pantalla en celu */
    h1 {
        font-size: 1.5rem !important;
        margin-bottom: 0px !important;
    }
    
    h3 {
        font-size: 1.1rem !important;
        margin-top: 0px !important;
    }

    /* 4. Reducir el espacio de las métricas */
    [data-testid="stMetric"] {
        padding: 5px !important;
    }
    
    /* 5. Forzar a que la tabla ocupe más espacio visual */
    .stDataFrame {
        margin-top: -10px !important;
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
        dorsal, nro_vuelta, hora_llegada, estado,
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

if evento:
    ranking = obtener_ranking_espejo(evento['id_evento'])
    
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

    
    # Header con Clima (Cronoer Style)
    st.title(f"🏆 {evento['nombre']}")
    st.subheader(f":{color_header}[{etiqueta}]") # Esto pone el texto en color
    st.write(f"### 📍 {evento['lugar']} | 🌡️ {evento.get('temperatura', '--')}°C | 💧 {evento.get('humedad', '--')}%")
    st.write(f"### 🌡️ {evento.get('temperatura', '--')}°C | 💧 {evento.get('humedad', '--')}%")

    st.caption(f"Clima: {evento.get('clima_desc', 'Sin datos')}")
    st.markdown("---")

    if not ranking.empty:
        # 1. Calculamos la métrica de activos de forma segura
        # Contamos las filas donde el estado es exactamente 'ACT'
        total_activos = int((ranking['estado'] == 'ACT').sum())

        # 2. Calculamos el patio actual (lógica de tiempo)
        hora_cero_local = pd.to_datetime(evento.get('hora_cero', datetime.now(timezone.utc)))
        ahora = datetime.now(timezone.utc)
        segundos_totales = (ahora - hora_cero_local).total_seconds()
        patio_actual = int(segundos_totales // 3600) + 1 if segundos_totales > 0 else 1
        
        # 3. Mostramos las métricas antes de la tabla
        col1, col2 = st.columns(2)
        with col1:
            # Calculamos el patio basándonos en la última vuelta registrada si ya terminó
            max_vuelta = ranking['nro_vuelta'].max()
            st.metric("Vuelta", f"#{max_vuelta}" if tiene_ganador else f"#{patio_actual}")
        with col2:
            st.metric("Atletas en carrera", total_activos)
        
        st.markdown("---")
        
        # 1. Calculamos KM
        ranking['KM'] = (ranking['nro_vuelta'] * 6.706).round(2)

        # 1. Mapeo de Banderas para Nacionalidad
        banderas = {
            "ARG": "🇦🇷 ARG",
            "URY": "🇺🇾 URY",
            "BRA": "🇧🇷 BRA",
            "CHL": "🇨🇱 CHL",
            "GER": "🇩🇪 GER",
            "ISR": "🇮🇱 ISR",
            "ESP": "🇪🇸 ESP",
            "USA": "🇺🇸 USA"
        }
        ranking['Pais'] = ranking['Pais'].map(lambda x: banderas.get(x, x))

        # Para mostrar un guion en lugar de 0
        ranking['PB'] = pd.to_numeric(ranking['PB'], errors='coerce').astype('Int64')
    
        # 2. CREAMOS una columna nueva para el tiempo neto (no sobreescribas la original aún)
        # Importante: asegurate que calcular_tiempo_neto devuelva el string
        ranking['tiempo_neto'] = ranking.apply(lambda x: calcular_tiempo_neto(x, hora_cero_local), axis=1)
        ranking['es_activo'] = ranking['estado'] == 'ACT'
        
        # 3. ORDENAMOS: 1° Vueltas (Desc), 2° Hora llegada real (Asc) para que el más rápido suba
        # Creamos una columna auxiliar para priorizar al Ganador
        ranking['es_ganador'] = ranking['estado'] == 'WINNER'
        
        # Ajustamos el orden: 
        # 1° Ganador (True arriba)
        # 2° Activos (True arriba)
        # 3° Mayor número de vueltas
        # 4° Menor tiempo de llegada (más rápido)
        ranking = ranking.sort_values(
            by=["es_ganador", "es_activo", "nro_vuelta", "hora_llegada"], 
            ascending=[False, False, False, True]
        )
        
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

        # 4. Definimos columnas (Cambiamos hora_llegada por tiempo_neto)
        columnas_visibles = ["dorsal", "Atleta", "Pais", "nro_vuelta", "estado","KM", "tiempo_neto", "PB"]
    
        st.dataframe(
            ranking[columnas_visibles].style.apply(color_filas, axis=1),
            column_config={
                "dorsal": "Bib",
                "Atleta": "Atleta",
                "Pais": "País",
                "nro_vuelta": "Vuelta",
                "estado": "Estado",
                "KM": st.column_config.NumberColumn("KM", format="%.2f"),
                # CAMBIO CLAVE AQUÍ: Usamos TextColumn porque 'tiempo_neto' es un String "MM:SS"
                "tiempo_neto": st.column_config.TextColumn("Última Vuelta"),
                "PB": st.column_config.NumberColumn(
                    "PB",
                    help="Personal Best (Patios)",
                    format="%i" # Usamos %i (integer) en lugar de %d para evitar el conflicto visual
                    #format="%d"  # El %d fuerza a mostrarlo como entero
                )
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
