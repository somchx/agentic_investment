"""Serve the compiled frontend and existing API on one HTTPS origin."""
from pathlib import Path
import os
from fastapi import HTTPException
from fastapi.responses import FileResponse
from app.main import app

PUBLIC = Path(os.environ.get('PUBLIC_DIR', '/app/public')).resolve()

@app.get('/{path:path}', include_in_schema=False)
def frontend(path: str):
    if path == 'api' or path.startswith('api/'):
        raise HTTPException(status_code=404)
    requested = (PUBLIC / path).resolve()
    if not requested.is_relative_to(PUBLIC):
        raise HTTPException(status_code=404)
    if requested.is_file():
        return FileResponse(requested)
    if Path(path).suffix:
        raise HTTPException(status_code=404)
    return FileResponse(PUBLIC / 'index.html')
