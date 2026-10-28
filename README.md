# CeylonTea IQ
### AI-Powered Intelligence Platform for Sri Lanka's Ceylon Tea Industry

CeylonTea IQ brings together tea auction price forecasting,
export-demand prediction, export planning, growing-zone intelligence,
export readiness assessment, and tea-batch traceability in one platform.

<<<<<<< HEAD
Key Features
- #### Auction Price Forecasting --- LSTM-based price forecasts for
  High, Medium, and Low Growns, with a combined sales-and-price
  forecasting pipeline.
- #### Export Demand Forecasting --- Forecasts monthly tea export
  volume using historical data and an LSTM model.
- #### AI Export Advisor --- Generates explainable export-planning
  recommendations using retrieved data, knowledge-base evidence, and
  an optional LLM.
- #### Export Readiness Index (ERI) --- Assesses readiness using
  forecast metrics, declared capacity, document checks, and
  quality-control readiness.
- #### Zone Intelligence --- Calculates weighted growing-zone scores
  using auction price, demand, buyer-preference proxies, and supplied
  evidence for other factors.
- #### Digital Tea Passport --- Records batch lifecycle events and
  verifies a SHA-256 hash-linked ledger.
- #### Authentication and Roles --- Supports Google sign-in for regular
  users and a protected Super Admin login with authenticator-based
  verification.
  
### Technology Stack
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
  
### Main Dashboard Pages
  Page                   Purpose
  /auction-price       Auction price forecasting
  /export-demand       Monthly export-volume forecasting
  /export-advisor      Evidence-grounded export recommendations
  /export-readiness    Export Readiness Index
  /digital-passport    Tea-batch traceability and ledger verification
  /zone-intelligence   Growing-zone quality scoring
  
### Project Structure
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
#### Getting Started
Prerequisites
- Python 3.12 environment (the repository includes commands using
  .venv312)
- Node.js and npm
- Git
- Optional: OpenAI API key or a local Ollama installation for
  LLM-based advisor responses
- Optional: Neon PostgreSQL database for deployed or shared account
  storage
  
### 1. Clone the Repository
git clone <your-repository-url>
cd <repository-folder>
Replace the placeholders with your Git repository URL and folder name.

### 2. Configure the Backend
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

### 3. Run the Backend
From the repository root, use the Python environment configured for the
project:
=======
### Repository Structure

```text
AI-Smart-Tea-Ecosystem/
├── backend/
├── frontend/
├── .gitignore
└── README.md
```

- **backend/** — Backend services and APIs for the system.
- **frontend/** — User interface and dashboard.
- **.gitignore** — Specifies files and directories excluded from Git tracking.
- **README.md** — Project documentation.

### Git Branches and Development Workflow

The project uses separate Git branches to organize component development and integrate features.

- `main` — Main project branch.
- `dev` — Development and integration branch.
- `feature/disease-intelligence` — Tea disease intelligence.
- `feature/diseases-intelligence-system` — Disease intelligence system development.
- `feature/export-intelligence` — Tea export intelligence.
- `feature/export-intelligence-another` — Additional export intelligence development.
- `feature/tea-grade-ai` — Tea grading and quality analysis.
- `feature/yield-intelligence` — Tea yield intelligence.

**Current development status:** The GitHub repository shows that the `dev` branch is 38 commits ahead of and 1 commit behind `main`. Review and test the changes before merging the branches.

### Component 04 – AI-Powered Tea Export Intelligence Platform

The Component 04 dashboard includes three pages designed to support tea export intelligence and decision-making.

The component focuses on using tea auction and export-related information to support market analysis, price forecasting, and export recommendations.


<<<<<<< HEAD
The Digital Passport page records batch events (collection, processing, quality checks, packing,
export, and receipt) in `backend/data/component04/passport_ledger.jsonl`. Every event includes the
previous record hash and its own SHA-256 hash; `GET /api/component04/digital-passports/verify`
checks the chain. This local prototype is tamper-evident but is not connected to a distributed
blockchain network. The ledger is gitignored because it can contain operational traceability data.
After saving a batch event, its passport page displays a QR code and provides a PNG download.
The QR opens that batch passport on the same frontend site; sellers should use the deployed,
phone-accessible site URL when generating codes for customers.

### Google Sign-In and Sign-Up

The frontend provides `/login` and `/signup`. Regular users authenticate with Google's OAuth 2.0
authorization-code flow. The Super Admin uses the email/password configured for initial setup and
must also verify a time-based code from Google Authenticator. On first Super Admin sign-in, scan the
displayed QR code and enter a current six-digit code; only after successful verification is the
authenticator secret saved (encrypted) in the configured database. Later Super Admin sign-ins
require a fresh code.
The password is stored as a scrypt hash, not plaintext.

Set `ADMIN_BOOTSTRAP_EMAIL=admin@gmail.com` and `ADMIN_BOOTSTRAP_PASSWORD` in the untracked
`backend/.env` before starting the backend. The bootstrap creates the protected Super Admin account
once. Do not put the password or encryption key in source control, the frontend environment, or logs.
Generate a Fernet key for `TOTP_ENCRYPTION_KEY` and keep it backed up securely; losing that key
prevents decrypting the saved authenticator secret. Generate one using:

```powershell
>>>>>>> 2c68846819ffcb209c73142239027eaef3ac089f
cd backend
python run.py
If the project uses its documented Windows virtual environment, activate
it first or run the Python executable from that environment.

After the first Super Admin password is accepted and its account appears in the database, remove
`ADMIN_BOOTSTRAP_PASSWORD` from the environment file; the scrypt password hash remains in the
database. Keep `TOTP_ENCRYPTION_KEY` unchanged for future authenticator logins.

Sign-up offers **Admin**, **Export Manager**, **Quality & Compliance Officer**, **Data Analyst**,
**Farmer / Seller**, and **Viewer / Buyer**. Admin, Export Manager, Quality & Compliance Officer,
and Data Analyst registrations remain pending until approved. An Admin can approve the staff roles;
only the Super Admin can approve Admin requests. Farmer / Seller and Viewer / Buyer registrations
are self-service. Pending and rejected accounts cannot start a session.

The Super Admin account cannot be changed or deactivated through user management. It is also
prevented from authenticating through Google OAuth; use its password and authenticator flow.

To add another Super Admin, sign in as the current Super Admin and open **User Management**.
Create an invitation under **Invite Super Admin**, then share the displayed one-time link using
a trusted channel. The link expires after 24 hours and can only be used once; it is not emailed
automatically. Creating a replacement link for the same email invalidates the previous link.
The invitee chooses a password (at least 12 characters) and sets up Google
Authenticator on their first password sign-in. The invitation token is stored hashed in the
database and is not included in server request logs because it is carried in the URL fragment.

To configure Google OAuth:

1. Open Google Cloud Console and create or select a project.
2. Configure the OAuth consent screen with the application name and support email. Add the test
   Google accounts while the consent screen is in testing mode.
3. Create an OAuth client ID of type **Web application**.
4. Add the app origin (for local development, `http://localhost:5173`) under Authorized JavaScript
   origins.
5. Add the backend callback as an Authorized redirect URI:
   `http://localhost:8000/api/auth/google/callback`.
6. Put the client ID and client secret in `backend/.env` as `GOOGLE_CLIENT_ID` and
   `GOOGLE_CLIENT_SECRET`. Set `GOOGLE_REDIRECT_URI` to the exact redirect URI above and
   `FRONTEND_URL=http://localhost:5173`.
7. Keep the bootstrap password, `TOTP_ENCRYPTION_KEY`, and OAuth credentials on the server; never
   add them to frontend environment variables.
8. Install backend dependencies and restart the API. Start the Vite frontend and open
   `http://localhost:5173/login` or `/signup`.

For production, register the HTTPS app origin and HTTPS callback with Google, set
`COOKIE_SECURE=true`, and serve the frontend and `/api` through the same site origin (or configure
an appropriately secured same-site deployment). Set `DATABASE_URL` in `backend/.env` to the Neon
PostgreSQL connection URL to store accounts, hashed sessions, OAuth state, audit records, and
passport ownership in Neon. The backend requires SSL for this connection and initializes the
required tables automatically. Leave `DATABASE_URL` empty to use SQLite locally; setting
`RBAC_DATABASE_PATH` explicitly selects SQLite even if `DATABASE_URL` is also set. Existing local
SQLite records are not copied to Neon automatically.

### Combined Workbook Auction Price Forecast

`backend/ml/datasets/raw/component04/Combined_Sales_Quantity_and_Price_Single_Sheet_2016_2026.xlsx`
contains weekly rows with repeated monthly price aggregates. The pipeline keeps one monthly average
price per month, compares baselines and ML regressors using rolling validation through 2024, tests on
2025, and refits the selected model through the latest available month for a 12-month forecast.

```powershell
.\.venv\Scripts\python.exe -m backend.ml.training.component04.train_combined_auction_price
```

The API endpoint is `/api/component04/combined-auction-price`; its chart and test predictions appear
on the Auction Price page.

The separate growing-zone auction pipeline stores its model metadata in
`backend/ml/models/component04/auction_lstm_model_info.json`.

### Train Again

```powershell
cd backend
.\.venv\Scripts\python.exe ml\preprocessing\component04\clean_auction_data.py
.\.venv\Scripts\python.exe ml\training\component04\train_lstm.py
```

### Run Backend

```powershell
cd backend
.\.venv\Scripts\python.exe run.py
```

### Run Dashboard

```powershell
cd frontend
npm install
npm run dev
Open the local URL printed by Vite, typically http://localhost:5173.

### Model Training
The repository includes separate pipelines for auction-price and
export-demand forecasting. Run these from the repository root using the
project's configured Python environment.

<<<<<<< HEAD
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

### Important Notes
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
=======
- `http://localhost:5173`
=======
>>>>>>> ddfab2352c38bb5f856adc60d0d69d19323e9544
>>>>>>> 2c68846819ffcb209c73142239027eaef3ac089f
