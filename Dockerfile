FROM debian:12-slim

WORKDIR /app

COPY src /app

RUN pip install -r requirements.txt

RUN python /app/app.py
