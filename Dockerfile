FROM python:3.14

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Self-signed TLS cert (valid 10 years) — needed for camera access on mobile browsers.
RUN mkdir -p /code/cert && openssl req -x509 -newkey rsa:2048 \
    -keyout /code/cert/key.pem -out /code/cert/cert.pem \
    -days 3650 -nodes \
    -subj "/CN=mangashelf" \
    -addext "subjectAltName=DNS:mangashelf.local,DNS:linovo.local,DNS:localhost,IP:127.0.0.1"

COPY ./app /code/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--ssl-keyfile", "/code/cert/key.pem", "--ssl-certfile", "/code/cert/cert.pem"]
