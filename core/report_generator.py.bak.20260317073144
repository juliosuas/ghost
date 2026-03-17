"""Professional investigation report generator — HTML/PDF/JSON output."""

import json
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ghost.core.config import BASE_DIR, INVESTIGATIONS_DIR


class ReportGenerator:
    """Generate investigation reports in multiple formats."""

    def __init__(self):
        """Initialize the report generator with a Jinja2 template environment."""
        template_dir = BASE_DIR / "templates"
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html"]),
        )

    def generate_report(
        self,
        investigation: dict,
        output_format: str = "html",
        output_path: str = None,
    ) -> str:
        """
        Generate a report and return the output path.

        Args:
            investigation: The investigation data.
            output_format: The desired output format (html, json, pdf).
            output_path: The path to save the report to. If None, a default path will be used.

        Returns:
            The output path of the generated report.
        """
        inv = investigation if isinstance(investigation, dict) else investigation.to_dict()

        if output_path is None:
            inv_dir = INVESTIGATIONS_DIR / inv["id"]
            inv_dir.mkdir(parents=True, exist_ok=True)
            ext = "json" if output_format == "json" else "html"
            output_path = str(inv_dir / f"report.{ext}")

        if output_format == "json":
            return self._generate_json_report(inv, output_path)
        elif output_format == "pdf":
            return self._generate_pdf_report(inv, output_path)
        else:
            return self._generate_html_report(inv, output_path)

    def _generate_html_report(self, inv: dict, output_path: str) -> str:
        """
        Generate an HTML report.

        Args:
            inv: The investigation data.
            output_path: The path to save the report to.

        Returns:
            The output path of the generated report.
        """
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

    def _generate_json_report(self, inv: dict, output_path: str) -> str:
        """
        Generate a JSON report.

        Args:
            inv: The investigation data.
            output_path: The path to save the report to.

        Returns:
            The output path of the generated report.
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(
            json.dumps(inv, indent=2, default=str), encoding="utf-8"
        )
        return output_path

    def _generate_pdf_report(self, inv: dict, output_path: str) -> str:
        """
        Generate a PDF report via HTML intermediate.

        Args:
            inv: The investigation data.
            output_path: The path to save the report to.

        Returns:
            The output path of the generated report.
        """
        html_path = output_path.replace(".pdf", ".html")
        self._generate_html_report(inv, html_path)
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
  /* ... */
</style>
</head>
<body>
  <!-- ... -->
</body>
</html>"""

    @staticmethod
    def _generate_pdf_report_intermediate(inv: dict, output_path: str) -> str:
        """
        Generate an intermediate HTML report for PDF conversion.

        Args:
            inv: The investigation data.
            output_path: The path to save the report to.

        Returns:
            The output path of the generated report.
        """
        # Implement PDF intermediate generation logic here
        pass
```

```python
# Example usage:
report_generator = ReportGenerator()
report_generator.generate_report(
    investigation={"id": "example", "target": "example_target"},
    output_format="html",
    output_path="path/to/report.html",
)