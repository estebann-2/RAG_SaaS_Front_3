# Utiliza la imagen base de Python 3.12.7 slim
FROM python:3.12.7-slim

# Establece variables de entorno para Python para evitar la generación de archivos .pyc
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Configura la variable de entorno LANG para establecer la configuración regional predeterminada para el contenedor
    LANG=C.UTF-8 \
    # Establece la zona horaria a Bogotá
    TZ=America/Bogota

# Instala los paquetes necesarios, incluidos locales y los requerimientos para tu aplicación
RUN apt-get update && \
    apt-get install -y \
        build-essential \
        pkg-config \
        curl \
        default-libmysqlclient-dev \
        locales \
        && \
    # Limpia el cache de apt para reducir el tamaño de la imagen
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copia el archivo de requisitos primero para aprovechar la caché de las capas de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código de la aplicación
COPY . .

# Expone el puerto en el que tu aplicación se ejecutará
EXPOSE 8000

# Ejecuta tu aplicación Django en todas las interfaces de red (0.0.0.0) y en el puerto 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
