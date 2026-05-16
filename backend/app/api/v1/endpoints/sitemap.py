from fastapi import APIRouter
from fastapi.responses import Response
from app.core.database import get_db

router = APIRouter()

BASE = "https://ecalt.vercel.app"

STATIC_ROUTES = [
    (f"{BASE}/", "1.0", "weekly"),
    (f"{BASE}/journeys", "0.9", "weekly"),
    (f"{BASE}/journey/journey-dna", "0.8", "monthly"),
    (f"{BASE}/journey/journey-ml", "0.8", "monthly"),
    (f"{BASE}/journey/journey-rockets", "0.8", "monthly"),
    (f"{BASE}/journey/journey-music", "0.8", "monthly"),
    (f"{BASE}/journey/journey-climate", "0.8", "monthly"),
    (f"{BASE}/journey/journey-finance", "0.8", "monthly"),
]


@router.get("", response_class=Response, summary="XML sitemap including AI-generated journeys")
async def sitemap():
    urls = list(STATIC_ROUTES)

    # Append public AI-generated journeys from DB
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM journeys WHERE is_curated = FALSE ORDER BY created_at DESC LIMIT 500"
                )
                for row in cur.fetchall():
                    urls.append((f"{BASE}/journey/{row['id']}", "0.6", "monthly"))
    except Exception:
        pass

    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, priority, freq in urls:
        parts.append(
            f"  <url><loc>{loc}</loc>"
            f"<priority>{priority}</priority>"
            f"<changefreq>{freq}</changefreq></url>"
        )
    parts.append("</urlset>")

    return Response(content="\n".join(parts), media_type="application/xml",
                    headers={"Cache-Control": "public, max-age=3600"})
