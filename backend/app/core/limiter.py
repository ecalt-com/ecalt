"""Rate limiting keyed by the real client IP (SC-009 / #19).

Measured on Railway dev (2026-11-05), the request reaches uvicorn from
Railway's internal proxy (`request.client.host` = 100.64.0.x), so keying on it
made every user share each limit. What arrives instead:

- `X-Real-IP` — set by Railway's edge to the TCP peer; a client-sent value is
  overwritten, so it can't be spoofed.
- Calls from the SPA come through the Vercel `/api/*` rewrite, so that peer is
  a Vercel egress IP. Vercel then sends the browser's IP in
  `x-vercel-forwarded-for` (overwriting any client value) plus
  `x-vercel-proxy-signature`.

So: X-Real-IP, or `x-vercel-forwarded-for` when the request carries Vercel's
proxy signature. Residual: a direct caller to the Railway domain can forge
both Vercel headers to rotate its key; set RATE_LIMIT_TRUST_VERCEL_HEADER=false
to key purely on X-Real-IP (then SPA users behind one Vercel edge share limits).
"""
import ipaddress
from typing import Optional

from slowapi import Limiter
from starlette.requests import Request

from app.core.config import settings


def _ip(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    candidate = value.split(",")[0].strip()
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def client_ip(request: Request) -> str:
    h = request.headers
    if settings.RATE_LIMIT_TRUST_VERCEL_HEADER and h.get("x-vercel-proxy-signature"):
        vercel = _ip(h.get("x-vercel-forwarded-for"))
        if vercel:
            return vercel
    return _ip(h.get("x-real-ip")) or (request.client.host if request.client else "unknown")


limiter = Limiter(key_func=client_ip)
