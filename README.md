# CeylonTea IQ
AI-Powered Intelligence Platform for Sri Lanka's Ceylon Tea Industry

CeylonTea IQ brings together tea auction price forecasting,
export-demand prediction, export planning, growing-zone intelligence,
export readiness assessment, and tea-batch traceability in one platform.
Key Features
- Auction Price Forecasting --- LSTM-based price forecasts for
  High, Medium, and Low Growns, with a combined sales-and-price
  forecasting pipeline.
- Export Demand Forecasting --- Forecasts monthly tea export
  volume using historical data and an LSTM model.
- AI Export Advisor --- Generates explainable export-planning
  recommendations using retrieved data, knowledge-base evidence, and
  an optional LLM.
- Export Readiness Index (ERI) --- Assesses readiness using
  forecast metrics, declared capacity, document checks, and
  quality-control readiness.
- Zone Intelligence --- Calculates weighted growing-zone scores
  using auction price, demand, buyer-preference proxies, and supplied
  evidence for other factors.
- Digital Tea Passport --- Records batch lifecycle events and
  verifies a SHA-256 hash-linked ledger.
- Authentication and Roles --- Supports Google sign-in for regular
  users and a protected Super Admin login with authenticator-based
  verification.
Technology Stack
- Frontend: React, Vite
- Backend: Python, FastAPI
- Machine Learning: TensorFlow/Keras, LSTM
- AI Recommendations: Retrieval-Augmented Generation (RAG),
  OpenAI-compatible LLM endpoints, optional local Ollama
- Database: SQLite for local development; PostgreSQL (Neon)
  supported
- Security: Google OAuth 2.0, role-based access control, scrypt
  password hashing, TOTP verification, Fernet-encrypted authenticator
  secrets
- Traceability: SHA-256 hash-linked event ledger
Main Dashboard Pages
  Page                   Purpose
  /auction-price       Auction price forecasting
  /export-demand       Monthly export-volume forecasting
  /export-advisor      Evidence-grounded export recommendations
  /export-readiness    Export Readiness Index
  /digital-passport    Tea-batch traceability and ledger verification
  /zone-intelligence   Growing-zone quality scoring
Project Structure
CeylonTea-IQ/
├── backend/
│   ├── ml/
│   │   ├── datasets/
│   │   ├── preprocessing/
│   │   ├── training/
│   │   └── models/
│   ├── data/
│   ├── .env
│   └── run.py
└── frontend/
This is a representative overview; exact folders may vary by repository
version.
Getting Started
Prerequisites
- Python 3.12 environment (the repository includes commands using
  .venv312)
- Node.js and npm
- Git
- Optional: OpenAI API key or a local Ollama installation for
  LLM-based advisor responses
- Optional: Neon PostgreSQL database for deployed or shared account
  storage
1. Clone the Repository
git clone <your-repository-url>
cd <repository-folder>
Replace the placeholders with your Git repository URL and folder name.
2. Configure the Backend
Create backend/.env and configure the environment variables required
by your setup. Common optional settings include:
LLM_API_KEY=
LLM_API_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

# Configure these only when enabling Google OAuth:
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback
FRONTEND_URL=http://localhost:5173
For local LLM use, start Ollama and download the configured model. The
advisor can fall back to explainable rule-based recommendations if the
configured LLM endpoint is unavailable.

Security: Never commit .env files, passwords, API keys, OAuth
secrets, encryption keys, or operational passport-ledger data to source
control. Follow the repository's environment configuration and
deployment requirements.
3. Run the Backend
From the repository root, use the Python environment configured for the
project:
cd backend
python run.py
If the project uses its documented Windows virtual environment, activate
it first or run the Python executable from that environment.
4. Run the Frontend
Open a second terminal:
cd frontend
npm install
npm run dev
Open the local URL printed by Vite, typically http://localhost:5173.
Model Training
The repository includes separate pipelines for auction-price and
export-demand forecasting. Run these from the repository root using the
project's configured Python environment.

Auction-price pipeline:
cd backend
python ml/preprocessing/component04/clean_auction_data.py
python ml/training/component04/train_lstm.py
Export-demand pipeline (from the repository root):
python -m backend.ml.training.component04.train_export_demand_lstm
Check the scripts and dataset paths in the repository before training.
Training time and results depend on the environment and available data.
API Overview
  Endpoint                                          Purpose
  POST /api/component04/export-advisor            Generate export-planning
                                                    recommendations

  POST /api/component04/export-readiness          Assess export readiness

  GET /api/component04/zone-intelligence          Retrieve growing-zone intelligence

  POST /api/component04/zone-intelligence/score   Calculate a zone score

  GET /api/component04/digital-passports/verify   Verify the digital-passport ledger
  GET /api/component04/export-demand              Export-demand forecast API
Confirm endpoint methods and availability against the current backend
implementation.
Important Notes
- Forecasts are model-based estimates and should be evaluated against
  relevant historical and real-world outcomes.
- The Export Readiness Index is a planning aid, not an official
  certification or destination-specific compliance assessment.
- Zone-level export-success and climate scores must be supported by
  evidence; unavailable observations should not be fabricated.
- The Digital Passport is a local tamper-evident prototype using a
  hash-linked ledger. It is not connected to a distributed blockchain
  network.
- Keep credentials and sensitive operational data out of Git.
License
Add the appropriate license and copyright information before public
distribution.
