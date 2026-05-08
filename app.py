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
            atletas:dni_atleta(nombre, apellido, nacionalidad)
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
            "Pais": atl.get('nacionalidad', 'ARG')
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
    # Definimos la hora de inicio del evento (asegúrate que en la base de datos esté como timestamp)
    # Si no existe el campo, usamos la hora actual como backup para que no rompa
    # Usamos 'hora_cero' que es el timestamp exacto de largada, no 'fecha_inicio'
    hora_cero_local = pd.to_datetime(evento.get('hora_cero', datetime.now(timezone.utc)))
    
    # Header con Clima (Cronoer Style)
    st.title(f"🏆 {evento['nombre']}")
    st.write(f"### 📍 {evento['lugar']} | 🌡️ {evento.get('temperatura', '--')}°C | 💧 {evento.get('humedad', '--')}%")
    st.caption(f"Clima: {evento.get('clima_desc', 'Sin datos')}")
    st.markdown("---")

    # Lógica mejorada para Activos
    # En un Backyard, los Activos son: Todos los que empezaron (Starters) 
    # MENOS los que ya quedaron fuera (DNF, DQ, etc.) en cualquier momento de la carrera.
    res_eliminados = supabase.table("vueltas_vivo") \
        .select("dorsal", count="exact") \
        .eq("id_evento", ID_EVENTO) \
        .neq("estado", "ACT") \
        .execute()
    
    total_fuera = res_eliminados.count if res_eliminados.count is not None else 0
    total_activos = total_starters - total_fuera
    
    # Y para la métrica "En Circuito":
    # Son los Activos que todavía no cruzaron la meta en ESTE patio.
    llegaron_ya = supabase.table("vueltas_vivo") \
        .select("dorsal", count="exact") \
        .eq("id_evento", ID_EVENTO) \
        .eq("nro_vuelta", patio) \
        .eq("estado", "ACT") \
        .execute()
            
    # 1. Contar cuántos tienen el estado 'ACT'
    # Usamos el conteo exacto de la base de datos
    #total_activos = res_activos.count if res_activos.count else 0
    # Forzamos que si total_activos quedó en 0 por alguna razón, sea al menos el nro de starters
    if total_activos == 0: total_activos = total_starters
    ya_en_base = llegaron_ya.count if llegaron_ya.count is not None else 0
    en_pista_real = total_activos - ya_en_base
    
    # SECCIÓN A: MÉTRICAS PRINCIPALES
    c1, c2, c3, c4 = st.columns(4) # Cambiamos a 4 columnas
    with c1:
        st.metric("Starters", total_starters) # Mostramos el total inicial
    with c2:
        st.metric("Vuelta Actual", patio)
    with c3:
        st_color = "inverse" if seg_restantes <= 180 else "normal"
        st.metric("Tiempo para Campana", crono, delta_color=st_color)
    with c4:
        # Mantenemos tu lógica de "En Pista / Activos"
        st.metric("En Circuito / Activos", f"{en_pista_count} / {total_activos}")

    ranking = obtener_ranking_espejo(evento['id_evento'])

    if not ranking.empty:
        # 1. Calculamos KM
        ranking['KM'] = (ranking['nro_vuelta'] * 6.706).round(2)
    
        # 2. CREAMOS una columna nueva para el tiempo neto (no sobreescribas la original aún)
        # Importante: asegurate que calcular_tiempo_neto devuelva el string
        ranking['tiempo_neto'] = ranking.apply(lambda x: calcular_tiempo_neto(x, hora_cero_local), axis=1)
        ranking['es_activo'] = ranking['estado'] == 'ACT'
        # 3. ORDENAMOS: 1° Vueltas (Desc), 2° Hora llegada real (Asc) para que el más rápido suba
        ranking = ranking.sort_values(
        by=["es_activo", "nro_vuelta", "hora_llegada"], 
        ascending=[False, False, True]
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
        columnas_visibles = ["dorsal", "Atleta", "Pais", "nro_vuelta", "KM", "tiempo_neto", "estado"]
    
        st.dataframe(
            ranking[columnas_visibles].style.apply(color_filas, axis=1),
            column_config={
                "dorsal": "Bib",
                "Atleta": "Atleta",
                "Pais": "País",
                "nro_vuelta": "Vueltas",
                "KM": st.column_config.NumberColumn("KM", format="%.2f"),
                # CAMBIO CLAVE AQUÍ: Usamos TextColumn porque 'tiempo_neto' es un String "MM:SS"
                "tiempo_neto": st.column_config.TextColumn("Última Vuelta"),
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
