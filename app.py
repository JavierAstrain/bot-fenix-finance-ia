import streamlit as st

st.title("🔑 Test de API Key")

# Prueba si se carga correctamente desde los secrets
api_key = st.secrets.get("OPENROUTER_API_KEY")

if api_key:
    st.success("✅ API Key encontrada")
    st.write(api_key)
else:
    st.error("❌ No se encontró OPENROUTER_API_KEY en secrets")
