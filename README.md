# PandaRank - ChatGPT Scraper

Automated ChatGPT conversation scraper using Playwright for research and analytics.

## Features

- 🤖 Automated ChatGPT interactions with configurable question pool
- 🕷️ Playwright-based scraping with full browser automation
- 📊 PostgreSQL storage with structured schema
- 🔄 APScheduler for periodic runs
- 📡 REST API for data access
- 📈 Prometheus metrics integration
- 🐳 Fully Dockerized deployment

## Quick Start

1. Clone the repository and set up environment:
```bash
cp .env.example .env
# Edit .env with your OpenAI credentials
```

2. Start all services:
```bash
make up
```

3. Check logs:
```bash
make logs
```

4. Access services:
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Metrics: http://localhost:8080/metrics

## Architecture

```
┌─────────────┐
│  Scheduler  │ → Runs every 10 minutes
└─────────────┘
       ↓
┌─────────────┐
│   Scraper   │ → Playwright + Chrome
└─────────────┘
       ↓
┌─────────────┐
│  PostgreSQL │ → Persistent storage
└─────────────┘
       ↓
┌─────────────┐
│  FastAPI    │ → REST endpoints
└─────────────┘
```

## API Endpoints

- `GET /runs` - List all scraping runs
- `GET /runs/{uuid}` - Get detailed run information
- `GET /export/ndjson` - Export data as NDJSON
- `GET /questions` - List question pool
- `GET /stats` - Get overall statistics

## Configuration

Key environment variables:

- `OPENAI_SESSION_TOKEN` - ChatGPT session token (preferred)
- `OPENAI_EMAIL` / `OPENAI_PWD` - Fallback credentials
- `SCRAPE_INTERVAL_SEC` - Seconds between runs (default: 600)
- `HEADLESS` - Run browser in headless mode (default: true)

## Development

Run locally:
```bash
cd scraper
pip install -r requirements.txt
playwright install chromium
python -m app.main
```

## Monitoring

Prometheus metrics available:
- `chatgpt_scrapes_total` - Total scrape attempts
- `chatgpt_scrapes_success` - Successful scrapes
- `chatgpt_scrapes_failed` - Failed scrapes
- `chatgpt_scrape_duration_seconds` - Scrape duration histogram

## License

See LICENSE file for details.