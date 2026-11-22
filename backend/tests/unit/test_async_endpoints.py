"""E2: an `async def` endpoint that awaits nothing but calls get_db() blocks the
single event loop (prod runs one uvicorn worker) for the length of every query.
Make it a plain `def` (FastAPI runs it in the threadpool). Endpoints that must
stay async because they schedule tasks with ensure_future/create_task are exempt;
wrap their DB work in run_in_threadpool instead."""
import ast
import pathlib

ENDPOINTS = pathlib.Path(__file__).resolve().parents[2] / "app" / "api" / "v1" / "endpoints"
VERBS = {"get", "post", "put", "patch", "delete"}


def _offenders() -> list[str]:
    found = []
    for f in sorted(ENDPOINTS.glob("*.py")):
        src = f.read_text()
        for node in ast.walk(ast.parse(src)):
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            if not any(isinstance(d, ast.Call) and getattr(d.func, "attr", "") in VERBS for d in node.decorator_list):
                continue
            body = ast.get_source_segment(src, node) or ""
            touches_db = "get_db(" in body or "_db(" in body
            awaits = any(isinstance(n, ast.Await) for n in ast.walk(node))
            needs_loop = "ensure_future" in body or "create_task" in body
            if touches_db and not awaits and not needs_loop:
                found.append(f"{f.name}:{node.lineno} {node.name}")
    return found


def test_no_async_endpoint_blocks_the_event_loop_without_awaiting():
    assert _offenders() == [], (
        "These `async def` endpoints call get_db() but never await: make them plain `def`:\n  "
        + "\n  ".join(_offenders())
    )
