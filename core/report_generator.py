"""Professional investigation report generator — HTML/PDF/JSON output."""

import json
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ghost.core.config import BASE_DIR, INVESTIGATIONS_DIR


class ReportGenerator:
    """Generate investigation reports in multiple formats."""

    def __init__(self):
        template_dir = BASE_DIR / "templates"
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html"]),
        )

    def generate(self, investigation, format: str = "html", output_path: str = None) -> str:
        """Generate a report and return the output path."""
        inv = investigation if isinstance(investigation, dict) else investigation.to_dict()

        if output_path is None:
            inv_dir = INVESTIGATIONS_DIR / inv["id"]
            inv_dir.mkdir(parents=True, exist_ok=True)
            ext = "json" if format == "json" else "html"
            output_path = str(inv_dir / f"report.{ext}")

        if format == "json":
            return self._generate_json(inv, output_path)
        elif format == "pdf":
            return self._generate_pdf(inv, output_path)
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
        )

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(html, encoding="utf-8")
        return output_path

    def _generate_json(self, inv: dict, output_path: str) -> str:
        """Generate a JSON report."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(
            json.dumps(inv, indent=2, default=str), encoding="utf-8"
        )
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
