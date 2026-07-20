"""AgentTrust — behavioral compliance layer for enterprise AI agent registries.

FastAPI entrypoint: mounts the API under /, seeds 4 demo agents into the
in-memory registry on startup (each auto-tested with BCT), and serves the
static dashboard at /dashboard.
"""
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Make `core` and `api` importable regardless of the process's working
# directory (uvicorn/pytest may be invoked from the repo root, agent-trust/,
# or elsewhere).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from api.routes import router, run_bct_and_update  # noqa: E402
from core.agent_registry import build_demo_agents, registry  # noqa: E402

DASHBOARD_DIR = Path(__file__).resolve().parent / "dashboard"


@asynccontextmanager
async def lifespan(_: FastAPI):
    for agent in build_demo_agents():
        registry.register(agent)
        run_bct_and_update(agent)
    yield


app = FastAPI(
    title="AgentTrust",
    description="Behavioral compliance layer for enterprise AI agent registries.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)
app.mount("/dashboard/assets", StaticFiles(directory=DASHBOARD_DIR), name="dashboard-assets")


@app.get("/dashboard")
def serve_dashboard() -> FileResponse:
    return FileResponse(DASHBOARD_DIR / "index.html")


@app.get("/")
def root() -> dict:
    return {
        "name": "AgentTrust",
        "docs": "/docs",
        "dashboard": "/dashboard",
    }
