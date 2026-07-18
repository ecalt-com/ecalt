"""One-time: generate + upload hero images for the curated SAMPLE_JOURNEYS.

Curated journeys live in code, not the DB, so this prints a hero_image_url
line per journey — paste each into its SAMPLE_JOURNEYS entry in
app/api/v1/endpoints/journeys.py. Costs ~6 images at the configured model.

Usage: cd backend && venv/bin/python scripts/generate_curated_heroes.py
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.api.v1.endpoints.journeys import SAMPLE_JOURNEYS  # noqa: E402
from app.services.image_service import (  # noqa: E402
    generate_hero_image,
    images_enabled,
    upload_journey_image,
)


async def main() -> None:
    if not images_enabled():
        sys.exit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set in backend/.env")
    for j in SAMPLE_JOURNEYS:
        try:
            data, model, content_type = await generate_hero_image(j)
            url = await upload_journey_image(j.id, data, content_type)
            print(f'{j.id}:\n    hero_image_url="{url}",  # {model}')
        except Exception as exc:
            print(f"{j.id}: FAILED — {exc}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
