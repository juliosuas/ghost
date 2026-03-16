# GHOST — AI-Powered OSINT Investigation Platform

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT">
  <img src="https://img.shields.io/badge/platform-linux%20%7C%20macos%20%7C%20windows-lightgrey.svg" alt="Platform">
</p>

**GHOST** is a comprehensive open-source intelligence (OSINT) platform that automates person and entity investigations using AI to correlate, analyze, and report findings.

---

## Features

- **Multi-Vector Investigation** — Search by name, email, phone, username, or photo
- **Username Enumeration** — Check 500+ platforms including social media, forums, and adult sites
- **Email Intelligence** — Breach checks, account discovery, domain WHOIS, validation
- **Phone OSINT** — Carrier lookup, location estimation, social media association
- **Social Media Deep Dive** — Instagram, Twitter/X, Facebook, LinkedIn, TikTok, Reddit analysis
- **Domain Recon** — WHOIS, DNS, subdomains, tech stack, SSL, Wayback Machine
- **Image Analysis** — EXIF extraction, reverse image search, face detection, geolocation
- **Dark Web Monitoring** — Ahmia search, breach databases, paste sites
- **AI-Powered Correlation** — LLM-driven pattern recognition, risk assessment, profile building
- **Professional Reports** — HTML/PDF/JSON with timelines, network graphs, risk scores
- **Web Dashboard** — D3.js entity graphs, map view, timeline, evidence gallery
- **Beautiful CLI** — Rich-powered interactive interface with progress tracking

## Quick Start

```bash
# Clone
git clone https://github.com/yourorg/ghost.git
cd ghost

# Install
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run CLI
python -m ghost.ui.cli

# Run Web Dashboard
python -m ghost.backend.server
```

## Docker

```bash
docker-compose up -d
# Dashboard at http://localhost:5000
```

## Configuration

Copy `.env.example` to `.env` and add your API keys:

| Key | Service | Required |
|-----|---------|----------|
| `OPENAI_API_KEY` | AI Analysis | Yes |
| `HIBP_API_KEY` | Have I Been Pwned | No |
| `SHODAN_API_KEY` | Shodan | No |
| `GOOGLE_CX` / `GOOGLE_API_KEY` | Google Custom Search | No |
| `TWITTER_BEARER_TOKEN` | Twitter/X API | No |
| `IPINFO_TOKEN` | IP Geolocation | No |

## Usage

### CLI

```bash
# Interactive mode
python -m ghost.ui.cli

# Direct investigation
python -m ghost.ui.cli --target "john.doe@example.com" --type email
python -m ghost.ui.cli --target "johndoe" --type username
python -m ghost.ui.cli --target "+15551234567" --type phone
python -m ghost.ui.cli --target "example.com" --type domain
```

### Python API

```python
from ghost.core.investigator import GhostInvestigator

investigator = GhostInvestigator()
report = investigator.investigate("johndoe", input_type="username")
report.export("report.html", format="html")
```

### REST API

```bash
curl -X POST http://localhost:5000/api/investigate \
  -H "Content-Type: application/json" \
  -d '{"target": "johndoe", "type": "username"}'
```

## Architecture

```
ghost/
├── core/           # Investigation orchestration & correlation
├── modules/        # OSINT collection modules
├── ai/             # LLM-powered analysis & summarization
├── ui/             # CLI and web dashboard
├── backend/        # Flask API server & database
├── templates/      # Report templates
└── tests/          # Test suite
```

## Legal Disclaimer

**WARNING: This tool is provided for authorized security research, journalism, law enforcement, and personal use only.**

- You are solely responsible for ensuring your use complies with all applicable local, state, national, and international laws
- Unauthorized surveillance, stalking, or harassment is illegal and unethical
- Always obtain proper authorization before investigating individuals
- Data collected may be subject to GDPR, CCPA, and other privacy regulations
- The developers assume no liability for misuse of this tool
- By using GHOST, you agree to use it only for lawful purposes

**Do not use this tool to:**
- Stalk, harass, or intimidate any person
- Violate any person's reasonable expectation of privacy
- Conduct unauthorized surveillance
- Bypass access controls or terms of service
- Engage in any illegal activity

## License

MIT License — see [LICENSE](LICENSE) for details.
