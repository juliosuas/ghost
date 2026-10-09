"""Professional investigation report generator — HTML/PDF/JSON/Markdown output."""

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from jinja2 import Environment, FileSystemLoader

from ghost.core.config import BASE_DIR, INVESTIGATIONS_DIR


def _template_dir() -> Path:
    """Locate report.html in the repo checkout or under the ghost package."""
    candidates = [
        Path(__file__).resolve().parents[2] / "templates",
        BASE_DIR / "templates",
        BASE_DIR.parent / "templates",
    ]
    for candidate in candidates:
        if (candidate / "report.html").is_file():
            return candidate
    return candidates[0]


_MD_SPECIALS = set("\\`*_{}[]()#+-.!|>")


def linkable_http_url(url: object) -> str:
    """Return url unchanged when it may be used as an href, otherwise ''.

    The stored value is never rewritten. javascript:, data:, and other
    schemes stay in the report as text and are not turned into links.
    """
    if not isinstance(url, str) or not url:
        return ""
    if any(ord(char) < 32 or char in " \t\"'<>\\" for char in url):
        return ""
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return ""
    return url


def escape_markdown(value: object) -> str:
    """Escape untrusted text for a Markdown document.

    HTML is escaped first so raw tags cannot render, then Markdown
    metacharacters are backslash-escaped so links, images, and headings
    cannot be injected.
    """
    if value is None:
        return ""
    text = html.escape(str(value), quote=True)
    return "".join("\\" + char if char in _MD_SPECIALS else char for char in text)


class ReportGenerator:
    """Generate investigation reports in multiple formats."""

    def __init__(self):
        template_dir = _template_dir()
        # autoescape=True covers report.html and the inline fallback. The
        # fallback is built with from_string(), which has no filename, so
        # select_autoescape() would leave ingested fields unescaped.
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True,
        )
        self.env.filters["linkable_url"] = linkable_http_url

    def generate(self, investigation, format: str = "html", output_path: str = None) -> str:
        """Generate a report and return the output path."""
        inv = investigation if isinstance(investigation, dict) else investigation.to_dict()
        inv = {**inv, "provenance": self._build_provenance(inv)}

        if output_path is None:
            inv_dir = INVESTIGATIONS_DIR / inv["id"]
            inv_dir.mkdir(parents=True, exist_ok=True)
            if format == "json":
                ext = "json"
            elif format in {"md", "markdown"}:
                ext = "md"
            else:
                ext = "html"
            output_path = str(inv_dir / f"report.{ext}")

        if format == "json":
            return self._generate_json(inv, output_path)
        elif format == "pdf":
            return self._generate_pdf(inv, output_path)
        elif format in {"md", "markdown"}:
            return self._generate_markdown(inv, output_path)
        else:
            return self._generate_html(inv, output_path)

    def _generate_html(self, inv: dict, output_path: str) -> str:
        """Generate an HTML report."""
        try:
            template = self.env.get_template("report.html")
        except Exception:
            # Fallback to inline template
            template = self.env.from_string(self._fallback_template())

        html = template.render(
            investigation=inv,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            findings=inv.get("findings", {}),
            correlations=inv.get("correlations", {}),
            ai_analysis=inv.get("ai_analysis", {}),
            summary=inv.get("summary", ""),
            risk_score=inv.get("risk_score", 0),
            errors=inv.get("errors", []),
            provenance=inv.get("provenance", {}),
        )

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(html, encoding="utf-8")
        return output_path

    def _generate_json(self, inv: dict, output_path: str) -> str:
        """Generate a JSON report."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json.dumps(inv, indent=2, default=str), encoding="utf-8")
        return output_path

    def _generate_markdown(self, inv: dict, output_path: str) -> str:
        """Generate a Markdown report with every untrusted field escaped."""
        lines = [
            "# Ghost investigation report",
            "",
            f"- **Target:** {escape_markdown(inv.get('target'))}",
            f"- **Type:** {escape_markdown(inv.get('input_type'))}",
            f"- **ID:** {escape_markdown(inv.get('id'))}",
            f"- **Status:** {escape_markdown(inv.get('status'))}",
            f"- **Scope:** {escape_markdown(inv.get('scope'))}",
            f"- **Authorized:** {'yes' if inv.get('authorized_use') else 'no'}",
            "",
            "## Summary",
            "",
            escape_markdown(inv.get("summary")),
            "",
            "## Ingested records",
            "",
        ]
        records = []
        ingest = inv.get("findings", {}).get("ingest") if isinstance(inv.get("findings"), dict) else None
        if isinstance(ingest, dict) and isinstance(ingest.get("records"), list):
            records = ingest["records"]
        if not records:
            lines.append("None.")
            lines.append("")
        for index, record in enumerate(records, start=1):
            if not isinstance(record, dict):
                lines.append(f"### {index}")
                lines.append("")
                lines.append(escape_markdown(record))
                lines.append("")
                continue
            provenance = record.get("provenance") if isinstance(record.get("provenance"), dict) else {}
            lines.extend(
                [
                    f"### {index}. {escape_markdown(record.get('platform'))}",
                    "",
                    f"- **Tool:** {escape_markdown(record.get('tool'))}",
                    f"- **Status:** {escape_markdown(record.get('status'))}",
                    f"- **Subject:** {escape_markdown(record.get('subject'))}",
                    f"- **URL:** {escape_markdown(record.get('url'))}",
                    f"- **Ingested at:** {escape_markdown(provenance.get('ingested_at'))}",
                    f"- **Source SHA-256:** {escape_markdown(provenance.get('source_sha256'))}",
                    f"- **Tool version:** {escape_markdown(provenance.get('tool_version'))}",
                    f"- **Fields:** {escape_markdown(json.dumps(record.get('fields'), default=str, ensure_ascii=True))}",
                    "",
                ]
            )
        lines.extend(["## Other findings", ""])
        findings = inv.get("findings", {}) if isinstance(inv.get("findings"), dict) else {}
        other = {key: value for key, value in findings.items() if key != "ingest"}
        lines.append(escape_markdown(json.dumps(other, indent=2, default=str, ensure_ascii=True)))
        lines.extend(
            [
                "",
                "## Errors",
                "",
                escape_markdown(json.dumps(inv.get("errors", []), default=str, ensure_ascii=True)),
                "",
                "## Provenance",
                "",
                escape_markdown(json.dumps(inv.get("provenance", {}), indent=2, default=str, ensure_ascii=True)),
                "",
            ]
        )
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text("\n".join(lines), encoding="utf-8")
        return output_path

    def _generate_pdf(self, inv: dict, output_path: str) -> str:
        """Generate a PDF report via HTML intermediate."""
        html_path = output_path.replace(".pdf", ".html")
        self._generate_html(inv, html_path)
        try:
            from weasyprint import HTML

            HTML(filename=html_path).write_pdf(output_path)
            return output_path
        except ImportError:
            return html_path  # Fallback to HTML if weasyprint unavailable

    def _build_provenance(self, inv: dict) -> dict:
        """Build audit metadata for defensible investigation reports."""
        findings = inv.get("findings", {})
        modules = sorted(findings)
        source_urls = []

        def collect_urls(value):
            if isinstance(value, dict):
                for key, nested in value.items():
                    if key == "url" and isinstance(nested, str) and nested.startswith(("http://", "https://")):
                        source_urls.append(nested)
                    else:
                        collect_urls(nested)
            elif isinstance(value, list):
                for item in value:
                    collect_urls(item)

        collect_urls(findings)

        module_errors = {
            module: data["error"] for module, data in findings.items() if isinstance(data, dict) and data.get("error")
        }

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "target": inv.get("target"),
            "input_type": inv.get("input_type"),
            "investigation_id": inv.get("id"),
            "scope": inv.get("scope", ""),
            "authorized_use": bool(inv.get("authorized_use", False)),
            "modules_run": modules,
            "module_count": len(modules),
            "source_urls": sorted(set(source_urls)),
            "source_url_count": len(set(source_urls)),
            "module_errors": module_errors,
            "global_errors": inv.get("errors", []),
        }

    def _fallback_template(self) -> str:
        return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Ghost Investigation Report — {{ investigation.target }}</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Courier New', monospace; background: #0a0a0a; color: #e0e0e0; padding: 2rem; }
  .header { border-bottom: 2px solid #00ff41; padding-bottom: 1rem; margin-bottom: 2rem; }
  .header h1 { color: #00ff41; font-size: 2rem; }
  .header .meta { color: #888; margin-top: 0.5rem; }
  .section { margin-bottom: 2rem; background: #111; border: 1px solid #222; border-radius: 4px; padding: 1.5rem; }
  .section h2 { color: #00ff41; margin-bottom: 1rem; border-bottom: 1px solid #333; padding-bottom: 0.5rem; }
  .risk-badge { display: inline-block; padding: 0.25rem 0.75rem; border-radius: 3px; font-weight: bold; }
  .risk-low { background: #1a3a1a; color: #00ff41; }
  .risk-medium { background: #3a3a1a; color: #ffff00; }
  .risk-high { background: #3a1a1a; color: #ff4141; }
  pre { background: #0d0d0d; padding: 1rem; border-radius: 4px; overflow-x: auto; font-size: 0.85rem; }
  .finding { margin-bottom: 1rem; padding: 0.75rem; border-left: 3px solid #00ff41; background: #0d0d0d; }
  .finding h3 { color: #41ff41; margin-bottom: 0.5rem; text-transform: uppercase; font-size: 0.9rem; }
  .error { border-left-color: #ff4141; }
  .footer { text-align: center; color: #555; margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #222; }
</style>
</head>
<body>
<div class="header">
  <h1>GHOST INVESTIGATION REPORT</h1>
  <div class="meta">
    Target: <strong>{{ investigation.target }}</strong> |
    Type: {{ investigation.input_type }} |
    ID: {{ investigation.id }} |
    Generated: {{ generated_at }}
  </div>
</div>

{% if summary %}
<div class="section">
  <h2>Executive Summary</h2>
  <p>{{ summary }}</p>
  {% if risk_score %}
  <p style="margin-top:1rem">Risk Score:
    <span class="risk-badge {% if risk_score < 0.4 %}risk-low{% elif risk_score < 0.7 %}risk-medium{% else %}risk-high{% endif %}">
      {{ "%.0f"|format(risk_score * 100) }}%
    </span>
  </p>
  {% endif %}
</div>
{% endif %}

{% for module, data in findings.items() %}
<div class="section">
  <h2>{{ module | upper }}</h2>
  {% if data is mapping and data.get('error') %}
  <div class="finding error"><h3>Error</h3><pre>{{ data.error }}</pre></div>
  {% else %}
  <pre>{{ data | tojson(indent=2) }}</pre>
  {% endif %}
</div>
{% endfor %}

{% if provenance %}
<div class="section">
  <h2>Provenance</h2>
  <p>Modules run: {{ provenance.modules_run | join(', ') }}</p>
  <p>Source URLs captured: {{ provenance.source_url_count }}</p>
  <pre>{{ provenance | tojson(indent=2) }}</pre>
</div>
{% endif %}

{% if correlations %}
<div class="section">
  <h2>Correlations & Connections</h2>
  <pre>{{ correlations | tojson(indent=2) }}</pre>
</div>
{% endif %}

{% if ai_analysis %}
<div class="section">
  <h2>AI Analysis</h2>
  <pre>{{ ai_analysis | tojson(indent=2) }}</pre>
</div>
{% endif %}

{% if findings.get('ingest') and findings.ingest.get('records') %}
<div class="section">
  <h2>Ingested Records</h2>
  {% for record in findings.ingest.records %}
  <div class="finding">
    <h3>{{ record.platform or 'Unknown' }}</h3>
    <p>{{ record.tool }} · {{ record.status }} · {{ record.subject }}</p>
    {% set href = record.url | linkable_url %}
    {% if href %}<p><a href="{{ href }}" rel="nofollow noopener noreferrer">{{ record.url }}</a></p>{% elif record.url %}<p>{{ record.url }}</p>{% endif %}
    {% if record.fields %}<pre>{{ record.fields | tojson(indent=2) }}</pre>{% endif %}
    {% if record.provenance %}<pre>{{ record.provenance | tojson(indent=2) }}</pre>{% endif %}
  </div>
  {% endfor %}
</div>
{% endif %}

{% if errors %}
<div class="section">
  <h2>Errors & Warnings</h2>
  {% for err in errors %}
  <div class="finding error"><pre>{{ err }}</pre></div>
  {% endfor %}
</div>
{% endif %}

<div class="footer">
  <p>Generated by GHOST OSINT Platform | {{ generated_at }}</p>
  <p style="color:#333;margin-top:0.5rem">For authorized use only. Handle with care.</p>
</div>
</body>
</html>"""
