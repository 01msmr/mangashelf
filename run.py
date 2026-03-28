"""
Entry point — generates a self-signed cert on first run, then starts uvicorn.
"""
import os
import ssl
import subprocess
import sys

BASE_DIR = os.path.dirname(__file__)
CERT_FILE = os.path.join(BASE_DIR, 'cert.pem')
KEY_FILE  = os.path.join(BASE_DIR, 'key.pem')


def _generate_cert():
    """Generate a self-signed certificate valid for 10 years."""
    subprocess.run([
        'openssl', 'req', '-x509', '-newkey', 'rsa:2048',
        '-keyout', KEY_FILE, '-out', CERT_FILE,
        '-days', '3650', '-nodes',
        '-subj', '/CN=mangashelf.local',
    ], check=True, capture_output=True)
    print('Self-signed certificate generated.')


if __name__ == '__main__':
    if not os.path.exists(CERT_FILE) or not os.path.exists(KEY_FILE):
        _generate_cert()

    import uvicorn
    uvicorn.run(
        'app.main:app',
        host='0.0.0.0',
        port=5001,
        ssl_certfile=CERT_FILE,
        ssl_keyfile=KEY_FILE,
        reload=False,
    )
