import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Equipment Triage Assistant")

@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

# Serve the built frontend
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):  # type: ignore
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
