# Agents — Recruiting ATS

AI-powered Applicant Tracking System for HR teams. Store job descriptions, upload resumes (including scanned PDFs), and get LLM-powered role-fit scoring with structured verification and suspicion detection.

**Stack:** FastAPI · React · SQLite · ChromaDB · Ollama (embeddings) · optional [Groq](https://groq.com) (fast LLM)

**Repository:** [github.com/Harish-nika/Agents](https://github.com/Harish-nika/Agents)

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
| **Dashboard charts** | Score distribution, role averages, verification gaps |

---

## Quick start (setup guide)

### 1. Clone

```bash
git clone https://github.com/Harish-nika/Agents.git
cd Agents/recruiting-agent
```

### 2. Prerequisites

- Python 3.10+
- Node.js 20+ (for frontend build)
- [Ollama](https://ollama.com) running locally

```bash
ollama pull llama3.1:8b
ollama pull nomic-embed-text
ollama pull qwen2.5:0.5b   # optional — faster JD parse / normalize
```

OCR for scanned resumes (Debian/Ubuntu):

```bash
sudo apt install tesseract-ocr poppler-utils
```

### 3. Secrets (never commit)

```bash
cp .env.example .env
# Edit .env — set APP_PASSWORD at minimum
```

| File | Purpose | In git? |
|------|---------|---------|
| `.env` | Login password, Ollama URLs, ports | **No** |
| `groq_key.txt` | Optional Groq API key | **No** |
| `resumes/` | Real candidate files for local testing | **No** |
| `data/` | SQLite DB, uploads, ChromaDB | **No** |

**Groq (optional):** Get a key at [console.groq.com](https://console.groq.com), then save it in **Settings → Groq API key** in the app (recommended) or in `groq_key.txt` locally.

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

Open `http://localhost:8512` — login: `hr` / password from `.env` (`APP_PASSWORD`).

### 5. First use

1. **Job Descriptions** — create a JD, paste content, click **Save** then **Index**
2. **Upload** — add resumes (or run `python scripts/reimport_resumes.py` with files in `resumes/`)
3. **Dashboard** — charts and pipeline health
4. **Results** — score comparison by role; **HR Questions** — verification queue

### 6. Production (systemd)

```bash
bash deploy/install.sh
sudo systemctl enable --now recruiting-agent
```

---

## Development

```bash
# API with reload
source venv/bin/activate && export PYTHONPATH=$(pwd)
uvicorn app.api.main:app --host 0.0.0.0 --port 8512 --reload

# React dev server (proxies /api → :8512)
cd frontend && npm run dev
```

Rebuild UI after changes: `cd frontend && npm run build`

---

## Project structure

```
Agents/
├── README.md                 # This monorepo overview
├── LICENSE
├── recruiting-agent/         # ATS / resume scoring agent
│   ├── app/
│   ├── frontend/
│   ├── deploy/
│   ├── scripts/
│   └── README.md
└── (future agents)/
```

---

## Analysis pipeline

```
Upload → Parse → Normalize → Verify → Embed → Search JDs → Suspicion → Score → HR questions
```

---

## Environment variables

| Variable | Description |
|----------|-------------|
| `APP_USERNAME` / `APP_PASSWORD` | HR login |
| `API_PORT` | Default `8512` |
| `OLLAMA_*` | Local models and URLs |
| `GROQ_*` | Model names when Groq key is set |
| `SUSPICION_THRESHOLD` | Default `60` |

---

## Testing

```bash
source venv/bin/activate && export PYTHONPATH=$(pwd)
python scripts/e2e_test.py
python scripts/reimport_resumes.py   # clear + score resumes/ folder
```

---

## Security

- Do not commit `.env`, `groq_key.txt`, or `resumes/`
- Change `APP_PASSWORD` before exposing on a network
- Groq sends text to Groq's API — use Ollama-only in Settings for fully local inference

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Ollama offline | `curl http://127.0.0.1:11434/api/tags` |
| Groq 429 | Space out uploads; retries are automatic |
| No results for a role filter | Candidates were scored against a different JD — use **All roles** or re-upload targeting that JD |
| Duplicate roles in filter | Archive old JDs you no longer use |
| Stale UI | `cd frontend && npm run build` then restart API |
| Reset DB | Delete `data/`, run `init_db()`, re-index JDs |

---

## License

MIT — see [LICENSE](LICENSE).
