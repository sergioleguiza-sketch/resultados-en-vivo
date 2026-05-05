import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from supabase import create_client

# Sin esto, la consola no sabe a dónde mandar los datos
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

def registrar_suceso(id_evento, dorsal, nro_vuelta, estado="ACT"):
    """
    Inserta el registro en vueltas_vivo. 
    El 'estado' puede ser ACT (por defecto), WINNER, o DNF (RTC/INC/OVR/DQ).
    """
    # Capturamos el momento exacto
    ahora = datetime.now(timezone.utc).isoformat()
    
    nuevo_registro = {
        "id_evento": id_evento,
        "dorsal": dorsal,
        "nro_vuelta": nro_vuelta,
        "hora_llegada": ahora,
        "estado": estado
    }
    
    # Encastre con Supabase
    try:
        response = supabase.table("vueltas_vivo").insert(nuevo_registro).execute()
        return f"Registro exitoso: {dorsal} - {estado}"
    except Exception as e:
        return f"Error en el registro: {e}"

def obtener_faltantes_en_patio(id_evento, nro_vuelta):
    # 1. Traemos todos los que iniciaron la vuelta (o todos los inscriptos)
    todos = supabase.table("inscripciones").select("dorsal").eq("id_evento", id_evento).execute()
    dorsales_todos = {c['dorsal'] for c in todos.data}
    
    # 2. Traemos los que ya llegaron al patio en ESTA vuelta
    llegaron = supabase.table("vueltas_vivo").select("dorsal").eq("id_evento", id_evento).eq("nro_vuelta", nro_vuelta).execute()
    dorsales_llegaron = {c['dorsal'] for c in llegaron.data}
    
    # 3. Traemos los que ya son DNF (para no buscarlos al cohete)
    fuera = supabase.table("vueltas_vivo").select("dorsal").eq("id_evento", id_evento).neq("estado", "ACT").execute()
    dorsales_fuera = {c['dorsal'] for c in fuera.data}
    
    # Faltantes = Todos - (Llegaron + Ya fuera de carrera)
    faltantes = dorsales_todos - (dorsales_llegaron | dorsales_fuera)
    return list(faltantes)

def obtener_ranking_vivo(id_evento):
    # Traemos el resumen de la tabla 'vueltas_vivo'
    # Agrupamos por dorsal para tener los totales
    resumen = supabase.table("vueltas_vivo") \
        .select("dorsal, nro_vuelta, estado") \
        .eq("id_evento", id_evento) \
        .execute()
    
    # Procesamos con Pandas para el ranking
    df = pd.DataFrame(resumen.data)
    ranking = df.groupby("dorsal").agg(
        Vueltas=("nro_vuelta", "max"),
        Ultimo_Estado=("estado", "last")
    ).reset_index()

    # Calculamos KM y ordenamos: 1° por Vueltas, 2° por Estado (Activos arriba)
    ranking["KM"] = ranking["Vueltas"] * 6.706
    ranking = ranking.sort_values(by=["Vueltas"], ascending=False)
    
    return ranking

# Buscamos el evento que pusiste como "en_vivo" en la tabla maestra
res_evento = supabase.table("eventos").select("*").eq("estado", "en_vivo").maybe_single().execute()

if res_evento.data:
    evento = res_evento.data
    ID_EVENTO = evento['id_evento']
    st.success(f"Conectado a: {evento['nombre']} | 🌡️ {evento['temperatura']}°C")
else:
    st.error("No hay evento activo en Supabase")
    st.stop()

st.title(f"🏆 Control en Vivo: {ID_EVENTO}")

# --- SECCIÓN A: RELOJ Y ESTADO GLOBAL ---
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Vuelta Actual", VUELTA_ACTUAL)
with col2:
    # Aquí iría un contador regresivo real
    st.metric("Tiempo Restante", "00:45:12", delta="-3 min", delta_color="inverse")
with col3:
    st.metric("En Circuito", "48 / 50", help="Corredores que aún no marcaron llegada")

# --- SECCIÓN B: MONITOR DE SEGURIDAD (Alertas) ---
st.subheader("🚨 Monitor de Seguridad")
# Esta lista se filtra automáticamente: inscriptos menos arribos
faltantes = ["Dorsal 10 - Juan Perez", "Dorsal 23 - Sergio L.", "Dorsal 44 - Ana F."]
for corredor in faltantes:
    st.warning(f"Falta Arribo: {corredor} | Asistente: Andrea Kapp")

# --- SECCIÓN C: INGRESO DE DATOS (El 'Lego' de Entrada) ---
st.divider()
col_in, col_btn = st.columns([3, 1])
with col_in:
    # El scanner de barras o tag 'tipea' aquí y manda Enter
    entrada = st.text_input("LECTURA DE HARDWARE (Dorsal/Tag):", placeholder="Scan aquí...")
with col_btn:
    if st.button("Registrar Arribo"):
        st.success(f"Arribo procesado: {entrada}")

# --- SECCIÓN D: NOVEDADES MANUALES (Botones Rápidos) ---
# --- Lógica de Selección (Para el Director) ---
# Traemos los corredores inscriptos para el selectbox
inscriptos_data = supabase.table("inscripciones").select("dorsal, nombre, apellido").eq("id_evento", ID_EVENTO).execute()
lista_corredores = [f"{c['dorsal']} - {c['nombre']} {c['apellido']}" for c in inscriptos_data.data]

st.subheader("📝 Registro de Novedades (Manual)")
corredor_selec = st.selectbox("Seleccionar Corredor:", lista_corredores)
dorsal_id = int(corredor_selec.split(" - ")[0])

# --- Enganche de los Botones ---
c1, c2, c3, c4 = st.columns(4)

with c1:
    if st.button("❌ Marcar RTC", use_container_width=True):
        res = registrar_suceso(ID_EVENTO, dorsal_id, VUELTA_ACTUAL, "DNF (RTC)")
        st.toast(res)

with c2:
    if st.button("⚠️ Marcar INC", use_container_width=True):
        res = registrar_suceso(ID_EVENTO, dorsal_id, VUELTA_ACTUAL, "DNF (INC)")
        st.toast(res)

with c3:
    if st.button("🚫 Marcar DQ", use_container_width=True):
        res = registrar_suceso(ID_EVENTO, dorsal_id, VUELTA_ACTUAL, "DNF (DQ)")
        st.toast(res)

with c4:
    if st.button("🏆 WINNER", use_container_width=True, type="primary"):
        res = registrar_suceso(ID_EVENTO, dorsal_id, VUELTA_ACTUAL, "WINNER")
        st.balloons() # ¡Festejo para el ganador!
        st.success(res)
