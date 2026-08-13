FROM python:3.11-alpine

WORKDIR /app

COPY server.py .

EXPOSE 9090

ENV LISTEN_PORT=9090

CMD ["python3", "server.py"]