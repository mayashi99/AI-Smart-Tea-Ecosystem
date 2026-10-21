import os
import sys
from pathlib import Path

import uvicorn


def use_project_venv():
    """Start with the repository's dependency-complete virtual environment.

    Component 02 requires the ML packages installed in ``backend/venv``. When
    this script is launched with a system Python, importing the FastAPI app
    fails before it can listen on port 8000, which in turn makes Vite report a
    misleading 502 proxy error.
    """
    backend_dir = Path(__file__).resolve().parent
    venv_python = backend_dir / "venv" / "bin" / "python"
    if venv_python.exists() and Path(sys.prefix).resolve() != (backend_dir / "venv").resolve():
        os.execv(str(venv_python), [str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]])


if __name__ == "__main__":
    use_project_venv()
    uvicorn.run("app.main:app", host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8000")), reload=True)
