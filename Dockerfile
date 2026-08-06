FROM python:3.13-slim

# Instalar dependencias del sistema necesarias para que Chromium y Playwright funcionen en Linux
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxcb1 \
    libxkbcommon0 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpangoft2-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar e instalar las librerías de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar el navegador Chromium para Playwright
RUN playwright install chromium

# Copiar el resto del código del proyecto
COPY . .

# Exponer el puerto
EXPOSE 8080

# Comando para iniciar la aplicación (Streamlit detectará el puerto automáticamente)
CMD ["streamlit", "run", "main.py", "--server.address=0.0.0.0"]