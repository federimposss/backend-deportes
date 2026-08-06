#!/bin/sh
# Asegurar que el puerto sea un número entero válido (por defecto 8080 si no está definido)
PORT_VAL="${PORT:-8080}"

# Sobrescribir la variable de Streamlit con el número real para evitar el error de '$PORT'
export STREAMLIT_SERVER_PORT="$PORT_VAL"

# Iniciar Streamlit usando el puerto numérico limpio
streamlit run main.py --server.port="$PORT_VAL" --server.address=0.0.0.0