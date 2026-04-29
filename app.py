import streamlit as st
from datetime import datetime

# Simulación de la configuración previa
ID_EVENTO = "Yaguarundi-2026"
HORA_LARGADA = datetime(2026, 9, 12, 8, 0, 0)
VUELTA_ACTUAL = 1

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
st.subheader("📝 Registro de Novedades (Manual)")
c1, c2, c3, c4 = st.columns(4)
with c1: st.button("❌ Marcar RTC", use_container_width=True)
with c2: st.button("⚠️ Marcar INC", use_container_width=True)
with c3: st.button("🚫 Marcar DQ", use_container_width=True)
with c4: st.button("⏳ Marcar OVR", use_container_width=True)
