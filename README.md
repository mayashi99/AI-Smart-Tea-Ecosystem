# AI-Smart-Tea-Ecosystem
AI-Powered Smart Tea Ecosystem for Sri Lankan Tea Industry

## Run the web application locally

Start the combined backend from the `backend` directory, using the Python
environment with FastAPI, Ultralytics and PyTorch installed:

```sh
cd backend
source venv/bin/activate
python -m uvicorn app.main:app --reload --port 8000
```

If a standalone harvest API is already running on port 8000, stop it with
Ctrl+C in its terminal before starting this command. The frontend needs the
combined app, which exposes both:

- `POST /component02/assess` — plantation health and climate assessment.
- `POST /component02/harvest-readiness/predict` — harvest readiness prediction.

Start the frontend in a second terminal from the project root:

```sh
cd frontend
npm run dev
```

Vite proxies both API routes to port 8000. `VITE_API_URL` can override the backend
base URL. The combined backend also allows direct requests from localhost and
127.0.0.1 on frontend ports 5173 and 4173.
