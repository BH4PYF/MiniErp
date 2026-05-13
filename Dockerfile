FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

EXPOSE 7777

CMD ["gunicorn", "--config", "deploy/gunicorn_config.py", "minierp.wsgi:application"]
