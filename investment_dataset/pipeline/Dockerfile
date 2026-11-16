FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-kor tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY investment_dataset/pipeline/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY investment_dataset /app/investment_dataset
ENV PYTHONPATH=/app/investment_dataset/pipeline
ENTRYPOINT ["python", "-m", "star_pipeline"]
CMD ["collect", "--root", "/app/investment_dataset", "--github-state"]
