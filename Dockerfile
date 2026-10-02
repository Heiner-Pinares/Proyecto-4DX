FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY . .
RUN useradd --create-home portal && mkdir -p staticfiles secrets runtime-config && chown -R portal:portal /app
USER portal
EXPOSE 8000
CMD ["python", "run.py"]
