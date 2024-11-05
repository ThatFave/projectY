FROM debian:12-slim

COPY src /app

RUN pip install -r requirements.txt

RUN python /app/app.py
