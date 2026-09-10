FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml ./
COPY src ./src
COPY app.py ./
COPY .streamlit ./.streamlit

RUN pip install --no-cache-dir --no-deps -e .

# Die Häufigkeitsdaten von wordfreq einmalig vorwärmen, damit der erste
# Aufruf im Betrieb nicht wartet.
RUN python -c "from wordfreq import zipf_frequency; zipf_frequency('test', 'en')"

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

CMD ["streamlit", "run", "app.py", "--server.port=8501"]
