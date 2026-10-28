# CeylonTea IQ

Ceylon tea intelligence platform for forecasting, export planning, market analysis, readiness, and traceability.

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
cd backend
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

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
npm run dev
```

Open the Vite URL shown in the terminal, usually:

- `http://localhost:5173`
=======
>>>>>>> ddfab2352c38bb5f856adc60d0d69d19323e9544
