# Agents — Recruiting ATS

AI-powered Applicant Tracking System for HR teams. Store job descriptions, upload resumes (including scanned PDFs), and get LLM-powered role-fit scoring with structured verification and suspicion detection.

**Stack:** FastAPI · React · SQLite · ChromaDB · Ollama (embeddings) · optional [Groq](https://groq.com) (fast LLM)

---

## Features

| Feature | Description |
|---------|-------------|
| **JD Manager** | Create/update roles; paste raw JD text → AI extracts skills and requirements |
| **Vector search** | JDs embedded with Ollama → ChromaDB semantic matching |
| **Resume upload** | PDF, DOCX, TXT, JPG/PNG; OCR for scanned documents |
| **Verification** | Structured extract (education, experience, projects) + anomaly rules |
| **Scoring** | Technical / HR / overall fit with strengths and gaps |
| **Suspicion + HR Qs** | Fraud flags and categorized verification questions |
| **Agent Activity** | Live pipeline timeline during analysis |

---

## Quick start

### 1. Clone

```bash
git clone https://github.com/Harish-nika/Agents.git
cd Agents
```

### 2. Prerequisites

- Python 3.10+
- Node.js 20+ (for frontend build)
- [Ollama](https://ollama.com) running locally

```bash
ollama pull llama3.1:8b
ollama pull nomic-embed-text
# Optional fast local model for JD parse / normalize:
ollama pull qwen2.5:0.5b
```

OCR (scanned resumes):

```bash
sudo apt install tesseract-ocr poppler-utils   # Debian/Ubuntu
```

### 3. Configure secrets (local only — never commit)

```bash
cp .env.example .env
# Edit .env — set APP_PASSWORD at minimum
```

| File | Purpose | Committed? |
|------|---------|------------|
| `.env` | App password, Ollama URLs, ports | **No** — gitignored |
| `groq_key.txt` | Optional Groq API key file | **No** — gitignored |
| `resumes/` | Real candidate PDFs for testing | **No** — gitignored |

**Groq (optional):** Sign up at [console.groq.com](https://console.groq.com), create an API key, then either:

- Save it in the app under **Settings → Groq API key** (recommended), or
- Create `groq_key.txt` in the project root (one line, gitignored)

Groq speeds up verification, scoring, and suspicion LLM calls. Embeddings still use Ollama.

### 4. Install and run

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -c "from app.db.models import init_db; init_db()"

cd frontend && npm install && npm run build && cd ..

export PYTHONPATH=$(pwd)
uvicorn app.api.main:app --host 0.0.0.0 --port 8512
```

Open `http://localhost:8512` — default login: username `hr`, password from `.env` (`APP_PASSWORD`).

### 5. First use

1. **Job Descriptions** — create or paste an active JD, then **Index** it
2. **Upload** — add resumes (or put files in `resumes/` and run `python scripts/reimport_resumes.py`)
3. **Results** — view scores; **HR Questions** — answer verification items

---

## Development

**API (reload):**

```bash
source venv/bin/activate
export PYTHONPATH=$(pwd)
uvicorn app.api.main:app --host 0.0.0.0 --port 8512 --reload
```

**React (hot reload):**

```bash
cd frontend && npm run dev   # http://localhost:5174 — proxies /api → :8512
```

**Production build after UI changes:**

```bash
cd frontend && npm run build
```

**Automated install (systemd):**

```bash
bash deploy/install.sh
sudo systemctl enable --now recruiting-agent
```

---

## Project structure

```
Agents/
├── app/
│   ├── api/              # FastAPI REST API
│   ├── services/         # Scoring, verification, parsers, vector store
│   └── db/models.py      # SQLite schema + migrations
├── frontend/             # React UI (Vite + TanStack Router)
├── deploy/               # systemd service, install scripts
├── scripts/
│   ├── e2e_test.py       # Full pipeline test
│   ├── benchmark_resumes.py
│   └── reimport_resumes.py   # Clear DB + analyze resumes/ folder
├── resumes/              # Local test resumes (gitignored)
├── data/                 # SQLite, ChromaDB, uploads (gitignored)
├── .env.example
└── requirements.txt
```

---

## Analysis pipeline

```
Upload → Parse → Normalize → Verify (structured + anomalies)
      → Embed → Search JDs → Suspicion → Score → Save HR questions
```

- **Verification gaps** always generate categorized HR questions
- **Suspicion score ≥ 60** adds additional LLM probe questions
- Duplicate emails on re-upload update the existing candidate

---

## Environment variables

See `.env.example`. Key settings:

| Variable | Description |
|----------|-------------|
| `APP_USERNAME` / `APP_PASSWORD` | HR login |
| `API_PORT` | Default `8512` |
| `OLLAMA_*` | Local models and URLs |
| `GROQ_*` | Model names when Groq key is set |
| `SUSPICION_THRESHOLD` | Default `60` |

---

## API

Base: `http://localhost:8512/api/v1`  
Auth: `POST /auth/login` → `Authorization: Bearer <token>`

Interactive docs: `http://localhost:8512/docs`

| Endpoint | Description |
|----------|-------------|
| `GET /candidates` | List candidates |
| `POST /candidates/upload` | Upload resume |
| `DELETE /candidates/{id}` | Delete one candidate + analyses |
| `DELETE /candidates` | Clear all candidates |
| `GET /hr-questions/grouped` | HR verification queue |
| `POST /candidates/{id}/reassess-suspicion` | Re-run after HR answers |

---

## Testing

```bash
source venv/bin/activate
export PYTHONPATH=$(pwd)

# End-to-end (no UI)
python scripts/e2e_test.py

# Score all files in resumes/ (uses saved Groq key if configured)
python scripts/reimport_resumes.py
```

---

## Security notes

- **Do not commit** `.env`, `groq_key.txt`, or files under `resumes/`
- Change `APP_PASSWORD` before any network exposure
- Groq sends resume/JD text to Groq's API — use Ollama-only mode in Settings if data must stay fully local
- Uploaded files are stored under `data/uploads/` (gitignored)

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Ollama offline | `curl http://127.0.0.1:11434/api/tags` — start Ollama |
| Groq 429 rate limit | Space out uploads; app retries automatically |
| No active JDs | Create and index a JD before uploading resumes |
| OCR fails | Install `tesseract-ocr` and `poppler-utils` |
| Stale UI | `cd frontend && npm run build` then restart API |
| Reset database | Stop app, delete `data/`, run `init_db()`, re-index JDs |

---

## License

MIT — see [LICENSE](LICENSE).

---

**Repository:** [github.com/Harish-nika/Agents](https://github.com/Harish-nika/Agents)
