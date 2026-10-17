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

Plantation Health checks uploaded image content before allowing analysis.
Install and provision the local screening model once from `backend`:

```sh
venv/bin/python -m pip install 'transformers>=4.45,<5'
venv/bin/python -m app.components.Component02.setup_image_validation
```

This downloads OpenAI CLIP ViT-B/32 weights; subsequent image checks run locally.
The `/component02/validate-images`, `/predict` and `/assess` routes reject
unreadable, oversized, unrelated or ambiguous images. If the screening model
is unavailable, validation returns HTTP 503 rather than allowing unchecked
health predictions. Each image must pass, including images in a mixed batch.
CLIP compares tea-related descriptions against unrelated subjects using a
similarity margin of 2.0. This is a preliminary zero-shot screen, not a validated
tea-species detector; other plants may pass and some tea photos may be rejected.
Calibrate it with representative tea and non-tea photos before production use.

Vite proxies both API routes to port 8000. `VITE_API_URL` can override the backend
base URL. The combined backend also allows direct requests from localhost and
127.0.0.1 on frontend ports 5173 and 4173.
