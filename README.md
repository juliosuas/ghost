<div align="center">

# 👻 GHOST

### AI-Powered OSINT Investigation Platform

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-linux%20%7C%20macos%20%7C%20windows-lightgrey.svg?style=for-the-badge)](#installation)
[![GitHub Stars](https://img.shields.io/github/stars/juliosuas/ghost?style=for-the-badge&logo=github)](https://github.com/juliosuas/ghost/stargazers)
[![GitHub Issues](https://img.shields.io/github/issues/juliosuas/ghost?style=for-the-badge)](https://github.com/juliosuas/ghost/issues)

**Multi-vector intelligence gathering with 500+ platform checks, AI-driven analysis, and professional reports.**

[Quick Start](#-quick-start) · [Features](#-features) · [Installation](#-installation) · [Documentation](#-usage) · [Roadmap](#-roadmap) · [Contributing](#-contributing)

---

*Automate OSINT investigations from a single target — name, email, phone, username, or photo — and let AI correlate everything into actionable intelligence.*

</div>

## 🔍 Why Ghost?

| Capability | Ghost | Maltego | SpiderFoot | Recon-ng |
|---|:---:|:---:|:---:|:---:|
| **AI-Powered Correlation** | ✅ | ❌ | ❌ | ❌ |
| **500+ Platform Checks** | ✅ | ✅¹ | ✅ | ~100 |
| **Professional HTML/PDF Reports** | ✅ | ✅ | ✅ | ❌ |
| **Web Dashboard with Graphs** | ✅ | ✅ | ✅ | ❌ |
| **Image/Face Analysis** | ✅ | ❌ | ❌ | ❌ |
| **Dark Web Monitoring** | ✅ | Plugin | ✅ | ❌ |
| **REST API** | ✅ | ❌ | ✅ | ❌ |
| **Beautiful CLI** | ✅ | ❌ | ✅ | ✅ |
| **100% Open Source** | ✅ | ❌ | ✅ | ✅ |
| **Zero Cost** | ✅ | ❌ | ✅ | ✅ |

<sup>¹ Requires paid transforms</sup>

## 📸 Screenshots

> **Coming soon** — Screenshots of the CLI, web dashboard, entity graph, and report output.

<!-- 
<div align="center">
  <img src="docs/screenshots/cli.png" width="45%" alt="Ghost CLI">
  <img src="docs/screenshots/dashboard.png" width="45%" alt="Web Dashboard">
</div>
-->

## ✨ Features

### Investigation Vectors

| Module | Description | Status |
|---|---|:---:|
| 🔤 **Username Enumeration** | Check 500+ platforms (social, forums, dating, adult) | ✅ |
| 📧 **Email Intelligence** | Breach checks, account discovery, WHOIS, validation | ✅ |
| 📱 **Phone OSINT** | Carrier lookup, location, social media association | ✅ |
| 🌐 **Domain Recon** | WHOIS, DNS, subdomains, tech stack, SSL, Wayback | ✅ |
| 🖼️ **Image Analysis** | EXIF extraction, reverse search, face detection, geolocation | ✅ |
| 🕵️ **Social Media Deep Dive** | Instagram, X, Facebook, LinkedIn, TikTok, Reddit | ✅ |
| 🌑 **Dark Web Monitoring** | Ahmia search, breach databases, paste sites | ✅ |

### Intelligence Engine

- 🤖 **AI Correlation** — LLM-driven pattern recognition across all data sources
- 📊 **Risk Assessment** — Automated risk scoring and threat profiling
- 🧩 **Entity Resolution** — Connect fragmented identities into unified profiles
- 📈 **Timeline Analysis** — Chronological activity mapping

### Output & Reporting

- 📄 **Professional Reports** — HTML, PDF, and JSON with network graphs and timelines
- 🗺️ **Web Dashboard** — D3.js entity graphs, map view, evidence gallery
- 🖥️ **Beautiful CLI** — Rich-powered interactive interface with live progress
- 🔌 **REST API** — Full programmatic access for automation pipelines

## 📦 Installation

### From Source (Recommended)

```bash
git clone https://github.com/juliosuas/ghost.git
cd ghost
pip install -r requirements.txt
cp .env.example .env   # Add your API keys
```

### With pip

```bash
pip install ghost-osint
```

### With Docker

```bash
git clone https://github.com/juliosuas/ghost.git
cd ghost
docker-compose up -d
# Dashboard → http://localhost:5000
```

## ⚡ Quick Start

```bash
# Interactive mode — guided investigation wizard
python -m ghost.ui.cli

# Investigate an email address
python -m ghost.ui.cli --target "john.doe@example.com" --type email

# Username hunt across 500+ platforms
python -m ghost.ui.cli --target "johndoe" --type username

# Phone number lookup
python -m ghost.ui.cli --target "+15551234567" --type phone

# Domain reconnaissance
python -m ghost.ui.cli --target "example.com" --type domain
```

## 🔧 Configuration

Copy `.env.example` to `.env` and add your API keys:

| Key | Service | Required | Free Tier |
|---|---|:---:|:---:|
| `OPENAI_API_KEY` | AI Analysis & Correlation | **Yes** | — |
| `HIBP_API_KEY` | Have I Been Pwned | No | ❌ |
| `SHODAN_API_KEY` | Shodan | No | ✅ |
| `GOOGLE_CX` / `GOOGLE_API_KEY` | Google Custom Search | No | ✅ |
| `TWITTER_BEARER_TOKEN` | Twitter/X API | No | ✅ |
| `IPINFO_TOKEN` | IP Geolocation | No | ✅ |

> **Note:** Ghost works with just an OpenAI key. Additional keys unlock more modules.

## 📖 Usage

### Python API

```python
from ghost.core.investigator import GhostInvestigator

investigator = GhostInvestigator()
report = investigator.investigate("johndoe", input_type="username")
report.export("report.html", format="html")
```

### REST API

```bash
# Start the server
python -m ghost.backend.server

# Submit an investigation
curl -X POST http://localhost:5000/api/investigate \
  -H "Content-Type: application/json" \
  -d '{"target": "johndoe", "type": "username"}'
```

## 🏗️ Architecture

```
ghost/
├── core/           # Investigation orchestration & correlation engine
├── modules/        # OSINT collection modules (username, email, phone, etc.)
├── ai/             # LLM-powered analysis, summarization & entity resolution
├── ui/             # CLI (Rich) and web dashboard
├── backend/        # Flask API server & SQLite database
├── templates/      # HTML/PDF report templates
├── data/           # Platform lists, signatures, patterns
└── tests/          # Test suite
```

## 🗺️ Roadmap

- [ ] **Plugin System** — Drop-in custom modules with standard interface
- [ ] **Geospatial Timeline** — Map-based activity visualization over time
- [ ] **Team Collaboration** — Multi-user investigations with shared workspaces
- [ ] **Telegram Bot** — Run investigations from Telegram
- [ ] **Export to STIX/TAXII** — Threat intelligence format compatibility
- [ ] **Graph Database** — Neo4j backend for complex relationship mapping
- [ ] **Mobile App** — iOS/Android companion for field investigations
- [ ] **Scheduled Monitoring** — Continuous target monitoring with alerts

## 🤝 Contributing

Contributions are welcome! Here's how to get started:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/amazing-module`
3. **Commit** your changes: `git commit -m "Add amazing module"`
4. **Push** to the branch: `git push origin feature/amazing-module`
5. **Open** a Pull Request

### Areas We Need Help

- 🌍 **New OSINT modules** — More platforms, more data sources
- 🧪 **Testing** — Unit tests, integration tests, edge cases
- 📝 **Documentation** — Guides, tutorials, API docs
- 🎨 **Dashboard UI** — Frontend improvements, new visualizations
- 🌐 **Translations** — i18n support for global users

## 💬 Community

- [GitHub Discussions](https://github.com/juliosuas/ghost/discussions) — Questions, ideas, show & tell
- [GitHub Issues](https://github.com/juliosuas/ghost/issues) — Bug reports & feature requests

## ⚠️ Legal Disclaimer

> **This tool is provided for authorized security research, journalism, law enforcement, and personal use only.**

By using Ghost, you agree to the following:

- You are **solely responsible** for ensuring your use complies with all applicable local, state, national, and international laws
- **Unauthorized surveillance, stalking, or harassment is illegal** and unethical
- Always obtain proper authorization before investigating individuals
- Data collected may be subject to **GDPR, CCPA**, and other privacy regulations
- The developers assume **no liability** for misuse of this tool

**Ghost must NOT be used to:**

| ❌ Prohibited Use |
|---|
| Stalk, harass, or intimidate any person |
| Violate any person's reasonable expectation of privacy |
| Conduct unauthorized surveillance |
| Bypass access controls or terms of service |
| Engage in any illegal activity |

*If you are unsure whether your use case is lawful, consult a legal professional before proceeding.*

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with 👻 by [Julio](https://github.com/juliosuas)**

*If Ghost helps your work, consider giving it a ⭐*

</div>

---
### 🌱 Also check out
**[AI Garden](https://github.com/juliosuas/ai-garden)** — A living world built exclusively by AI agents. Watch it grow.
