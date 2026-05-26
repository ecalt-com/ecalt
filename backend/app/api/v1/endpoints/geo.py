import httpx
from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/country")
async def get_country(request: Request):
    """Detect user country from IP. Returns ISO 3166-1 alpha-2 code."""
    # Prefer Cloudflare header (zero-latency, no external call)
    cf_country = request.headers.get("cf-ipcountry")
    if cf_country and cf_country != "XX":
        return {"country": cf_country}

    ip = request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"http://ip-api.com/json/{ip}?fields=countryCode")
            if r.status_code == 200:
                code = r.json().get("countryCode", "US")
                return {"country": code}
    except Exception:
        pass

    return {"country": "US"}
