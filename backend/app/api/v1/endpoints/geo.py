import httpx
from fastapi import APIRouter, Request

from app.core.config import settings

router = APIRouter()

_PRIVATE_PREFIXES = ("127.", "10.", "192.168.", "::1", "fc", "fd")


@router.get("/country")
async def get_country(request: Request):
    """Detect user country from IP. Returns ISO 3166-1 alpha-2 code."""
    # Prefer Cloudflare header (zero-latency, no external call)
    cf_country = request.headers.get("cf-ipcountry")
    if cf_country and cf_country != "XX":
        return {"country": cf_country}

    ip = request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()

    # Private/loopback IPs can't be geolocated — use configured default
    if any(ip.startswith(p) for p in _PRIVATE_PREFIXES):
        return {"country": settings.GEO_DEFAULT_COUNTRY}

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"http://ip-api.com/json/{ip}?fields=countryCode")
            if r.status_code == 200:
                code = r.json().get("countryCode") or settings.GEO_DEFAULT_COUNTRY
                return {"country": code}
    except Exception:
        pass

    return {"country": settings.GEO_DEFAULT_COUNTRY}
