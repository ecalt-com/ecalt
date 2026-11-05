from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def client_ip(request: Request) -> str:
    return get_remote_address(request)


limiter = Limiter(key_func=client_ip)
