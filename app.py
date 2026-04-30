import streamlit as st
import pandas as pd
import google.generativeai as genai
from fpdf import FPDF
import datetime
import io

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Analizador de Crédito Corporativo", layout="wide")

# --- ESTILOS PERSONALIZADOS ---
st.markdown("""
    <style>
    .main {
        background-color: #f5f7f9;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #003366;
        color: white;
    }
    .stDownloadButton>button {
        width: 100%;
        border-radius: 5px;
        background-color: #28a745;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

# --- INICIALIZACIÓN DE API GEMINI ---
apiKey = "" # El entorno proporciona la clave automáticamente
genai.configure(api_key=apiKey)

def call_gemini_with_retry(prompt, system_instruction):
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash-preview-09-2025",
        system_instruction=system_instruction
    )
    
    retries = 5
    for i in range(retries):
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception:
            if i == retries - 1:
                return "Error: No se pudo conectar con la IA después de varios intentos. Por favor, intenta de nuevo más tarde."
            import time
            time.sleep(2**i)

# --- CARGA DE DATOS DE REFERENCIA ---
@st.cache_data
def load_reference_data():
    try:
        # Cargamos los archivos proporcionados por el usuario
        base_datos = pd.read_csv("SAMITEX_LC_BASE_DATOS.xlsx - BASE DE DATOS LC.csv")
        instrucciones = pd.read_csv("SAMITEX_LC_BASE_DATOS.xlsx - INSTRUCCIONES PARA IA.csv")
        return base_datos, instrucciones
    except Exception as e:
        st.error(f"Error al cargar archivos de referencia: {e}")
        return None, None

df_base, df_instrucciones = load_reference_data()

# --- FUNCIONES DE PDF ---
def generate_pdf(data_summary, ai_analysis):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, txt="Resumen de Análisis de Línea de Crédito", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, txt=f"Fecha: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='R')
    
    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(200, 10, txt="Datos del Solicitante:", ln=True)
    pdf.set_font("Arial", size=11)
    
    for key, value in data_summary.items():
        pdf.multi_cell(0, 8, txt=f"{key}: {value}")
        
    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(200, 10, txt="Análisis y Sugerencia de la IA:", ln=True)
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 8, txt=ai_analysis)
    
    return pdf.output(dest='S').encode('latin-1', errors='replace')

# --- INTERFAZ DE USUARIO ---
st.title("🏦 Sistema de Sugerencia de Línea de Crédito")
st.subheader("Análisis inteligente basado en historial corporativo")

with st.form("credit_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        empresa_solicitada = st.selectbox("Empresa donde solicita el crédito", 
                                          ["Samitex", "Global Sourcing", "Primatex", "Texcorp"])
        equifax_ruc = st.text_area("Estado Equifax de la Empresa (RUC)", placeholder="Ej: 55k NOR (BCP), Deuda actual 8k normal...")
        equifax_rrll = st.text_area("Estado Equifax Rep. Legal (Opcional)", placeholder="Ej: Sin info en bancos / 20k Normal")
        partidas = st.text_input("Partidas / Propiedades", placeholder="Ej: 03 Partidas RRLL")

    with col2:
        compras_2024 = st.number_input("Monto de Compras 2024 (S/.)", min_value=0.0, step=1000.0)
        compras_2025 = st.number_input("Monto de Compras 2025 (S/.)", min_value=0.0, step=1000.0)
        referencias = st.text_area("Referencias Comerciales", placeholder="Ej: Buen pagador con Protex, Limite 20k")
        comentarios = st.text_area("Comentarios Extras", placeholder="Avales, incrementos previos, etc.")

    st.markdown("---")
    st.write("🔗 **Líneas de Crédito Existentes en la Corporación**")
    c1, c2, c3, c4 = st.columns(4)
    lc_samitex = c1.number_input("LC Samitex", min_value=0.0)
    lc_global = c2.number_input("LC Global Sourcing", min_value=0.0)
    lc_primatex = c3.number_input("LC Primatex", min_value=0.0)
    lc_texcorp = c4.number_input("LC Texcorp", min_value=0.0)

    submit_button = st.form_submit_button("🔍 Analizar Crédito")

# --- LÓGICA DE ANÁLISIS ---
if submit_button:
    with st.spinner("Analizando datos con Gemini Pro..."):
        # Preparar contexto para la IA
        contexto_base = ""
        if df_base is not None:
            # Tomamos una muestra representativa o resumen para no saturar tokens
            resumen_base = df_base.head(20).to_string()
            contexto_base = f"Base de datos de referencia (ejemplos):\n{resumen_base}"
            
        instrucciones_texto = ""
        if df_instrucciones is not None:
            instrucciones_texto = df_instrucciones.to_string()

        system_prompt = f"""
        Eres un Analista de Riesgos Senior especializado en el sector textil peruano. 
        Tu objetivo es sugerir una Línea de Crédito (LC) justa basada en los datos del usuario y la lógica de negocio de la corporación.
        
        LOGICA DE NEGOCIO REQUERIDA:
        {instrucciones_texto}
        
        REGLAS DE ORO:
        1. La LC sugerida suele rondar el 15-30% del volumen de compras anual (dar más peso a 2025).
        2. Si Equifax tiene estados 'DUD' (Dudoso) o 'PERD' (Pérdida), sé muy conservador o rechaza.
        3. 'NOR' (Normal) con montos altos amerita mayor LC.
        4. Las partidas registradas aumentan la confianza.
        5. Considera la exposición total del grupo (sumando las LC existentes en las otras 3 empresas).
        """
        
        user_input_prompt = f"""
        Analiza al siguiente cliente:
        - Empresa Solicitada: {empresa_solicitada}
        - Equifax RUC: {equifax_ruc}
        - Equifax RRLL: {equifax_rrll}
        - Partidas: {partidas}
        - Compras 2024: S/. {compras_2024}
        - Compras 2025: S/. {compras_2025}
        - Referencias: {referencias}
        - Comentarios: {comentarios}
        - LC Actuales en Grupo: Samitex({lc_samitex}), Global({lc_global}), Primatex({lc_primatex}), Texcorp({lc_texcorp})
        
        Proporciona:
        1. Sugerencia de Monto de Línea de Crédito.
        2. Justificación detallada basada en los puntos anteriores.
        3. Nivel de Riesgo (Bajo, Medio, Alto).
        """
        
        analisis_ia = call_gemini_with_retry(user_input_prompt, system_prompt)
        
        st.session_state['last_analysis'] = analisis_ia
        st.session_state['last_data'] = {
            "Empresa Destino": empresa_solicitada,
            "RUC Equifax": equifax_ruc,
            "Compras 2025": f"S/. {compras_2025}",
            "Partidas": partidas,
            "Exposición Grupal Total": f"S/. {lc_samitex + lc_global + lc_primatex + lc_texcorp}"
        }

if 'last_analysis' in st.session_state:
    st.markdown("### 📋 Resultado del Análisis")
    st.info(st.session_state['last_analysis'])
    
    # Botón para descargar PDF
    pdf_bytes = generate_pdf(st.session_state['last_data'], st.session_state['last_analysis'])
    st.download_button(
        label="📥 Descargar Resumen en PDF",
        data=pdf_bytes,
        file_name=f"analisis_credito_{datetime.datetime.now().strftime('%Y%m%d')}.pdf",
        mime="application/pdf"
    )

# --- PIE DE PÁGINA ---
st.markdown("---")
st.caption("Desarrollado para la Corporación. Arriba Alianza. 💙⚪")
