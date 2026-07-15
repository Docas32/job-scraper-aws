# Usa a imagem oficial do Playwright com Python, já com Chromium e dependências do SO instaladas
FROM mcr.microsoft.com/playwright/python:v1.45.0-noble

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia apenas o requirements.txt primeiro para aproveitar o cache de camadas do Docker
COPY requirements.txt .

# Instala as dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código-fonte (scripts .py e arquivos .json)
COPY *.py ./
COPY *.json ./

# Comando final: roda o scraper e, em caso de sucesso, o transform_and_load
CMD ["sh", "-c", "python scraper.py && python transform_and_load.py"]