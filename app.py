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
