import socket


def get_host_address() -> str:
    """Return <hostname>.local for mDNS resolution on the local network."""
    return socket.gethostname() + '.local'
