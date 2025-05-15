FROM python:3.13-slim

# Instala dependências do sistema para compilar mysqlclient
RUN apt-get update && apt-get install -y \
  gcc \
  default-libmysqlclient-dev \
  libssl-dev \
  pkg-config \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
