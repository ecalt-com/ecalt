#!/usr/bin/env python3
"""Smoke-test every GET endpoint of a deployed ECALT API.

Enumerates GET routes directly from the FastAPI app (so the list never goes
stale), substitutes dummy values for path parameters, and calls each route on
the target deployment. Nothing is written: only GET requests are sent.

Pass criteria (liveness, not correctness):
  PASS  2xx/3xx          public route works
  PASS  401/403/405/422/429  route is alive and guarded (auth, validation, rate limit)
  WARN  404              route defined in code but absent/flag-gated on the target
                         (e.g. SCHOOLS_ENABLED=false, or prod running an older build)
  FAIL  5xx, timeout, connection error

Usage:
  python scripts/api_smoke_test.py dev
  python scripts/api_smoke_test.py prod
  python scripts/api_smoke_test.py https://some-url.example.com
  python scripts/api_smoke_test.py dev --token <firebase-id-token>   # also exercise authed paths
  python scripts/api_smoke_test.py dev --filter /schools             # subset of routes

Exit code: 0 if no FAILs, 1 otherwise — safe to wire into CI as an
integration gate after a deploy.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

# The app only needs to be importable — point the DB at a dead socket so the
# import can never touch a real database.
os.environ.setdefault("DATABASE_URL", "postgresql://x:y@127.0.0.1:1/none")
os.environ.setdefault("SCHEDULER_ENABLED", "false")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx  # noqa: E402
from fastapi.routing import APIRoute  # noqa: E402

from app.main import app  # noqa: E402

BASE_URLS = {
    "dev": "https://ecalt-api-dev.up.railway.app",
    "prod": "https://ecalt-production.up.railway.app",
}

# Dummy substitutions for path parameters. Values only need to be
# syntactically plausible — guarded routes will 401/403/404 before using them.
PARAM_DUMMIES = {
    "int": "1",
    "str": "smoke-test-dummy",
}

CONCURRENCY = 8
TIMEOUT = 30.0


def iter_get_routes():
    for route in app.routes:
        if isinstance(route, APIRoute) and "GET" in route.methods:
            yield route


def fill_path(route: APIRoute) -> str:
    path = route.path
    for name, param in route.param_convertors.items():
        kind = type(param).__name__.lower()
        dummy = PARAM_DUMMIES["int"] if "integer" in kind else PARAM_DUMMIES["str"]
        path = path.replace("{" + name + "}", dummy)
    return path


def classify(status: int) -> str:
    if status < 400 or status in (401, 403, 405, 422, 429):
        return "PASS"
    if status == 404:
        return "WARN"
    return "FAIL"


async def check(client: httpx.AsyncClient, sem: asyncio.Semaphore, path: str):
    async with sem:
        try:
            resp = await client.get(path)
            return path, classify(resp.status_code), str(resp.status_code)
        except httpx.HTTPError as exc:
            return path, "FAIL", type(exc).__name__


async def run(base_url: str, token: str | None, path_filter: str | None) -> int:
    paths = sorted({fill_path(r) for r in iter_get_routes()})
    if path_filter:
        paths = [p for p in paths if path_filter in p]
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    sem = asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient(
        base_url=base_url, headers=headers, timeout=TIMEOUT, follow_redirects=False
    ) as client:
        results = await asyncio.gather(*(check(client, sem, p) for p in paths))

    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for path, verdict, detail in sorted(results, key=lambda r: (r[1] != "FAIL", r[1] != "WARN", r[0])):
        counts[verdict] += 1
        if verdict != "PASS":
            print(f"{verdict:4} {detail:>22}  {path}")
    print(f"\n{base_url}: {counts['PASS']} passed, {counts['WARN']} warned (404), "
          f"{counts['FAIL']} failed — {len(results)} GET routes checked")
    return 1 if counts["FAIL"] else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", help="'dev', 'prod', or a full base URL")
    parser.add_argument("--token", help="Firebase ID token to send as Bearer auth", default=None)
    parser.add_argument("--filter", dest="path_filter", help="only check paths containing this substring")
    args = parser.parse_args()
    base_url = BASE_URLS.get(args.target, args.target)
    if not base_url.startswith("http"):
        parser.error(f"unknown target {args.target!r} — use dev, prod, or a URL")
    return asyncio.run(run(base_url, args.token, args.path_filter))


if __name__ == "__main__":
    raise SystemExit(main())
