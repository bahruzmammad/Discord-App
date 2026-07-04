# 🛰️ OSINT Intelligence System

> **One system. One feed. Zero noise.**

A production-ready, open-source intelligence system designed for social media detox and unified information delivery. Replaces X, Reddit, and news feed consumption with a single structured intelligence stream delivered automatically to Discord.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.3+-5865F2.svg)](https://discordpy.readthedocs.io/)
[![No API Keys Required](https://img.shields.io/badge/API%20Keys-Not%20Required-green.svg)](#)

---

## What It Does

The system continuously collects high-signal public information from dozens of sources, deduplicates and ranks it, clusters related stories, and delivers one clean daily intelligence digest to your Discord channel — automatically.

**Data sources (all public, no authentication):**

| Category | Sources |
|---|---|
| 🌐 Tech News | TechCrunch, Wired, Ars Technica, The Verge, BBC, Reuters, NYT, MIT Tech Review |
| 💻 Programming | Hacker News, dev.to, Stack Overflow Blog, Netflix/AWS/Google/Meta blogs, InfoQ |
| 🔬 CS Research | arXiv (AI, DS, DC, NI, CR), Papers With Code, Distill.pub, IEEE Spectrum |
| 🔒 Cybersecurity | NVD/NIST CVEs, CISA KEV catalog, GitHub Security Advisories, Krebs, BleepingComputer |
| 🕵️ OSINT | EFF, Access Now, Tech Policy Press, CISA alerts |
| 📦 Open Source | GitHub Trending (6 languages), Linux Foundation, LWN.net, Opensource.com |
| 📰 Dev Communities | Reddit (28 curated subreddits), GitHub public search API |

**Processing pipeline:**

```
Collect → Deduplicate → Rank → Cluster → Digest → Discord
```

---

## Architecture

```
intelligence-system/
├── main.py                    # Entry point — wires everything together
├── config/
│   └── settings.py            # Environment-based config (no API keys)
├── models/
│   └── article.py             # Unified Article schema + Category enum
├── providers/                 # Data source adapters (pluggable)
│   ├── base.py                # Abstract BaseProvider
│   ├── rss_provider.py        # 40+ RSS/Atom feeds
│   ├── github_provider.py     # GitHub Trending + Search API
│   ├── reddit_provider.py     # 28 public subreddits
│   ├── security_provider.py   # NVD, CISA KEV, GHSA, security RSS
│   └── news_provider.py       # News RSS (15 public feeds, no API key)
├── core/                      # Processing engine
│   ├── aggregator.py          # Orchestrates all providers (async)
│   ├── deduplicator.py        # URL fingerprint + fuzzy title matching
│   ├── ranker.py              # Composite scoring: recency × credibility × signal
│   ├── clusterer.py           # TF-IDF + cosine similarity clustering
│   ├── digest.py              # Top-N per category, ordered digest report
│   └── pipeline.py            # Full pipeline: collect → dedup → rank → cluster → digest
├── bot/
│   ├── discord_bot.py         # discord.py bot: connect, send, close
│   └── formatter.py           # Embed builder, plain-text formatter
├── scheduler/
│   └── jobs.py                # APScheduler: daily digest + periodic alerts
├── services/
│   └── intelligence_service.py  # Top-level orchestrator (pipeline → bot)
├── utils/
│   ├── logger.py              # Rich/JSON/plain logging
│   ├── http_client.py         # Shared aiohttp session, rate limiting, retries
│   └── errors.py              # Custom exception hierarchy
├── tests/                     # Pytest test suite (no network calls)
│   ├── test_models.py
│   ├── test_deduplicator.py
│   ├── test_ranker.py
│   ├── test_clusterer.py
│   └── test_digest.py
├── requirements.txt
├── .env.example               # Template — no API keys required
├── setup.cfg                  # Pytest + coverage config
├── archive.sh                 # Creates a deployable ZIP
└── LICENSE                    # MIT
```

### Scoring Algorithm

Each article receives a composite `relevance_score` (0.0–1.0):

```
score = recency(0.30) + credibility(0.25) + raw_signal(0.20) + keywords(0.15) + category(0.10)
```

- **Recency**: Exponential decay with 24-hour half-life — today's news scores much higher than yesterday's
- **Credibility**: Source-specific multipliers (arXiv/NVD = 1.0 → random blog = 0.55)
- **Raw signal**: Normalised provider scores (GitHub stars, Reddit upvotes, CVSS score)
- **Keywords**: Regex-based boost for high-value terms (RCE, zero-day, LLM, breakthrough…)
- **Category**: Time-sensitive categories (cybersecurity) are weighted higher

---

## Quick Start

### Prerequisites

- Python 3.10 or higher
- A Discord bot token ([create one here](https://discord.com/developers/applications))
- A Discord server with a channel where the bot has `Send Messages` permission

### 1. Clone and install

```bash
git clone https://github.com/your-org/osint-intelligence.git
cd osint-intelligence
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` and fill in the **one required value**:

```env
DISCORD_BOT_TOKEN=your_bot_token_here
```

That's it. No channel IDs, no API keys, nothing else. The bot automatically selects the best channel to post to when it connects. Everything else has sensible defaults — see [Configuration](#configuration) for optional tuning.

### 3. Test with dry run (no Discord needed)

```bash
DRY_RUN=true python main.py
```

This runs the full pipeline and prints the digest to stdout — no Discord connection required.

### 4. Run

```bash
python main.py
```

The bot connects to Discord and waits for the scheduled digest time (default: **08:00 UTC**). It runs indefinitely as a background service.

### 5. Run once and exit

```bash
RUN_ONCE=true python main.py
```

Useful for testing delivery or running via cron.

---

## Configuration

All configuration is via environment variables (set in `.env`).

| Variable | Default | Description |
|---|---|---|
| `DISCORD_BOT_TOKEN` | **required** | Your Discord bot token — the only credential needed |
| `DIGEST_TIME_UTC` | `08:00` | Daily digest delivery time (HH:MM UTC) |
| `ALERT_INTERVAL_HOURS` | `0` | Trending alert interval in hours (0 = disabled) |
| `MAX_ITEMS_PER_PROVIDER` | `50` | Max articles collected per provider |
| `DIGEST_TOP_N` | `8` | Max articles per category in digest |
| `MIN_RELEVANCE_SCORE` | `0.25` | Minimum score threshold for digest inclusion |
| `DEDUP_THRESHOLD` | `0.75` | Fuzzy-match threshold for deduplication |
| `HTTP_TIMEOUT` | `20` | HTTP request timeout in seconds |
| `EXTRA_RSS_FEEDS` | *(empty)* | Comma-separated extra RSS URLs |
| `LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING / ERROR |
| `LOG_FORMAT` | `rich` | `rich` / `json` / `plain` |
| `LOG_FILE` | *(empty)* | Optional log file path |
| `DRY_RUN` | `false` | Process but don't post to Discord |
| `RUN_ONCE` | `false` | Run one cycle then exit |

---

## Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application** → name it "OSINT Intelligence"
3. Go to **Bot** → **Reset Token** → copy the **Token**
4. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot`
   - Bot Permissions: `Send Messages`, `Embed Links`, `Read Message History`
5. Open the generated URL → invite the bot to your server
6. Put `DISCORD_BOT_TOKEN=<your token>` in `.env` — that's everything

**Channel auto-selection:** on startup the bot looks for a text channel named `intelligence-digest` → `osint-digest` → `osint` → `general` → first writable channel, in that order. Create a channel named `intelligence-digest` in your server to control where digests land.

---

## Running Tests

```bash
# Run all unit tests
pytest

# With coverage report
pytest --cov=. --cov-report=term-missing

# Exclude slow/network tests
pytest -m "not integration"

# Verbose output
pytest -v
```

---

## Adding a New Provider

1. Create `providers/your_provider.py`:

```python
from providers.base import BaseProvider
from models.article import Article, Category

class YourProvider(BaseProvider):
    name = "your_provider"

    async def fetch(self) -> list[Article]:
        # Fetch data, normalise to Article objects, return list
        ...
```

2. Register it in `core/aggregator.py`:

```python
from providers.your_provider import YourProvider

_PROVIDER_CLASSES = [
    ...,
    YourProvider,
]
```

That's it. The pipeline picks it up automatically.

---

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for full VPS, AWS EC2, and systemd service instructions.

**Quick summary:**

```bash
# VPS / EC2 — run as systemd service
sudo cp deploy/osint-intelligence.service /etc/systemd/system/
sudo systemctl enable --now osint-intelligence

# Docker (optional)
docker build -t osint-intelligence .
docker run -d --env-file .env --name osint osint-intelligence

# Cron (minimal, no bot process)
RUN_ONCE=true python main.py   # add to crontab
```

---

## GitHub Setup

```bash
git init
git add .
git commit -m "feat: initial OSINT Intelligence System"
git remote add origin https://github.com/YOUR_USERNAME/osint-intelligence.git
git branch -M main
git push -u origin main
```

---

## Design Philosophy

- **Signal over noise**: aggressive filtering and scoring keeps only genuinely useful information
- **Zero social media**: replaces X, Reddit browsing, and news feeds — not supplements them
- **No API keys required**: every data source is publicly accessible
- **Modular and replaceable**: each provider, processor, and output adapter can be swapped independently
- **Async-first**: all I/O is non-blocking; providers run concurrently
- **Defensive only**: cybersecurity coverage is limited to public vulnerability databases, vendor advisories, and educational security research — no offensive security content

---

## Legal & Ethical Notice

This system collects data exclusively from:
- Public RSS/Atom feeds
- Official public APIs (GitHub, NVD/NIST, CISA)
- Public web pages (GitHub Trending, Reddit JSON API)

All data sources are legally accessible. The system:
- Respects `robots.txt` conventions
- Includes rate-limiting between requests per hostname
- Uses descriptive User-Agent strings
- Does not scrape authenticated or restricted content
- Does not collect or store personal data

---

## Contributing

Pull requests welcome. Please open an issue first for significant changes.

1. Fork the repo
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Add tests for new providers or core changes
4. Submit a PR

---

## License

[MIT](LICENSE) — free to use, modify, and distribute.
