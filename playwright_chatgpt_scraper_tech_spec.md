# PandaRank – Playwright‑Driven ChatGPT Scraper

## 1 – Purpose & Scope

This project automates the collection of ChatGPT conversational data for research or analytics.  It periodically burns through a **question pool** (customisable) and captures, for every run:

- **Prompt** that was sent
- **Assistant reply** (raw markdown)
- **Browsing traces** – every URL the assistant opened while answering
- **Timestamped screenshots** and full DOM dumps (optional)
- **Network waterfall** to let us replay/inspect all requests made

All artefacts are persisted in a structured database **and** optionally exported as newline‑delimited JSON.

---

## 2 – High‑Level Requirements

|  ID     | Requirement                                                                      | Priority |
| ------- | -------------------------------------------------------------------------------- | -------- |
|  FR‑01  | Pull prompts from a configurable pool (file / DB)                                | P0       |
|  FR‑02  | Schedule autonomous runs at a configurable interval                              | P0       |
|  FR‑03  | Log in to chat.openai.com via Playwright and maintain a session                  | P0       |
|  FR‑04  | Submit a prompt and wait until the response is fully streamed                    | P0       |
|  FR‑05  | Capture browsing panel events ("Searching …", "Visiting …") and the final answer | P0       |
|  FR‑06  | Store everything in **PostgreSQL** using an auditable schema                     | P0       |
|  FR‑07  | Provide an HTTP API to fetch raw/exported data                                   | P1       |
|  FR‑08  | Expose Prometheus metrics (job status, latency, failures)                        | P1       |
|  NFR‑01 | Entire stack launches with `docker‑compose up ‑d ‑‑build`                        | P0       |
|  NFR‑02 | All secrets / tunables via environment variables                                 | P0       |
|  NFR‑03 | Codebase linted + 90 % test coverage                                             | P2       |

---

## 3 – System Overview

```
                ┌─────────────┐
                │  Scheduler  │┐
                └─────┬───────┘│ cron/APS
                      │        │
                      ▼        │
┌────────────┐ 1. fetch     ┌──────────────┐
│ Question DB │────────────▶│ Scraper Svc  │
└────────────┘              └─────┬────────┘
                                   │2. Playwright headless
                                   ▼
                         chat.openai.com (Chromium)
                                   │3. network intercept
                                   ▼
                          ┌────────────────┐
                          │  Ingest Queue  │(Kafka optional)
                          └─────┬──────────┘
                                ▼
                          ┌──────────────┐
                          │   PostgreSQL │
                          └──────────────┘
```

### Containers

1. **scraper** – Python 3.11 + Playwright + our code
2. **postgres** – official image, volume‑backed
3. **api** (optional) – FastAPI exposing REST endpoints
4. **prometheus + grafana** (optional) – monitoring stack

---

## 4 – Key Components

### 4.1 Scheduler

- Uses **APScheduler** inside the scraper container
- Job ID: `ask_chatgpt`
- Interval configurable with `SCRAPE_INTERVAL_SEC` (default 600)

### 4.2 Question Pool Manager

- Source: YAML or DB table `questions`
- Columns: `id`, `text`, `cooldown_min`, `last_asked_at`
- Strategy: weighted‑random pick favouring least‑recently‑asked

### 4.3 Playwright Scraper Logic

1. **Session bootstrap**
   - Cookie import via `OPENAI_SESSION_TOKEN` (preferred)
   - Fallback: credentials `OPENAI_EMAIL`/`OPENAI_PWD` + MFA handler hook
2. **Prompt submission** – send text, await full streaming (`.typing‑cursor` gone)
3. **Event hooks**
   - `page.on("console")` – detect browsing messages
   - `page.on("requestfinished")` – filter domain patterns (google.com, wikipedia, …)
4. **Capture artefacts**
   - HTML after render (`page.content()`)
   - Screenshot (`page.screenshot()`)
   - HAR (`browserContext.tracing.start/stop`) – optional heavy flag

### 4.4 Data Layer

```sql
CREATE TABLE conversations (
  id               SERIAL PRIMARY KEY,
  run_uuid         UUID NOT NULL,
  question_id      INT  NOT NULL,
  started_at       TIMESTAMPTZ,
  finished_at      TIMESTAMPTZ
);

CREATE TABLE messages (
  id              SERIAL PRIMARY KEY,
  conversation_id INT REFERENCES conversations(id),
  role            TEXT CHECK (role IN ('user','assistant','system')),
  content_md      TEXT,
  scraped_at      TIMESTAMPTZ
);

CREATE TABLE web_searches (
  id              SERIAL PRIMARY KEY,
  conversation_id INT REFERENCES conversations(id),
  url             TEXT,
  title           TEXT,
  fetched_at      TIMESTAMPTZ
);
```

### 4.5 API Service (FastAPI)

- `GET /runs?since=` – list runs
- `GET /runs/{uuid}` – full nested JSON
- `GET /export/ndjson` – streaming export

---

## 5 – Docker Deployment

### 5.1 docker‑compose.yml (excerpt)

```yaml
version: "3.9"
services:
  scraper:
    build: ./scraper
    container_name: pandarank-scraper
    environment:
      - OPENAI_SESSION_TOKEN=${OPENAI_SESSION_TOKEN}
      - SCRAPE_INTERVAL_SEC=600
      - DB_DSN=postgresql://scraper:secret@db:5432/chatlogs
      - TZ=Asia/Tokyo
    depends_on:
      - db
    ports:
      - "${SCRAPER_PORT:-8080}:8080"  # metrics / healthz

  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      - POSTGRES_USER=scraper
      - POSTGRES_PASSWORD=secret
      - POSTGRES_DB=chatlogs
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "${DB_PORT:-5432}:5432"

  api:
    build: ./api
    depends_on:
      - db
    ports:
      - "${API_PORT:-8000}:8000"

volumes:
  pgdata:
```

### 5.2 Environment Variables

| Var                    | Example                | Meaning               |
| ---------------------- | ---------------------- | --------------------- |
| `OPENAI_SESSION_TOKEN` | `sess‑abc…`            | Auth cookie value     |
| `SCRAPE_INTERVAL_SEC`  | `600`                  | Seconds between jobs  |
| `DB_DSN`               | `postgresql://…`       | DB connect string     |
| `QUESTION_POOL_PATH`   | `/data/questions.yaml` | Path to pool file     |
| `HEADLESS`             | `true`                 | Run Chromium headless |

---

## 6 – Sequence Diagram

```
Scheduler ──► Scraper │ (trigger)
Scraper ──► ChatGPT   │ (login)
Scraper ──► ChatGPT   │ (prompt)
ChatGPT  ──► Scraper  │ (streamed tokens)
Scraper  ──► ChatGPT  │ (browsing sub‑requests)
Scraper  ──► DB       │ (persist artefacts)
Scraper  ──► Metrics  │ (update Prometheus)
```

---

## 7 – Testing & Quality Gates

- **Unit tests** (pytest + pytest‑playwright fixtures)
- **Integration test**: spins up full stack in CI using GitHub Actions + `--headed` for VNC recording
- **Security**: Trivy scans + dependabot
- **Linting**: ruff + mypy, pre‑commit enforced

---

## 8 – Roadmap

| Phase          | Deliverables                                         | ETA   |
| -------------- | ---------------------------------------------------- | ----- |
|  α (week 1‑2)  | Basic login, prompt, response capture → local SQLite | DD+14 |
|  β (week 3‑4)  | Dockerise, Postgres, scheduler, YAML question pool   | DD+30 |
| RC (week 5)    | API, Prometheus, CI/CD, docs                         | DD+37 |
|  v1.0 (week 6) | HAR capture, Grafana dashboards, NDJSON export       | DD+44 |

---

## 9 – Future Enhancements

- Add **proxy rotation** + residential exit nodes to avoid geo‑CAPTCHA
- Multi‑account support (credential pool)
- Redact PII in answers before storage
- Train an LLM to tag answer quality or hallucinations

---

## 10 – Appendices

### A – Sample `questions.yaml`

```yaml
- id: 1
  text: "Explain Bellman‑Ford vs Dijkstra in one tweet"
  cooldown_min: 1440
- id: 2
  text: "Write a bash one‑liner to find duplicate files"
  cooldown_min: 720
```

### B – Makefile Targets (excerpt)

```
make playwright‑install   # installs browsers
make dev                  # poetry run app locally
make compose‑up           # docker‑compose up -d --build
make test                 # run full test suite
```

---

© 2025 Panda Villa Tech Ltd – internal use

