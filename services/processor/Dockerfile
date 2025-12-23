FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY shared /app/shared
COPY services/processor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/processor .

CMD ["python", "main.py"]
