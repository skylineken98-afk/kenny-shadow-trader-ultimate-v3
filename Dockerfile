FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home kst && mkdir -p /backups && chown kst:kst /backups
USER kst
CMD ["python", "-m", "kst_chat.server"]
