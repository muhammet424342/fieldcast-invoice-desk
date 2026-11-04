FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY invoice_desk ./invoice_desk
COPY samples ./samples
ENV DATA_DIR=/data
VOLUME /data
EXPOSE 8010
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8010", "invoice_desk.app:app"]
