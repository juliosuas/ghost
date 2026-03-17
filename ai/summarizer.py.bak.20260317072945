"""Generate executive summaries of investigations."""

import json
from typing import Any

from ghost.core.config import Config


class OSINTSummarizer:
    """Generate concise executive summaries of OSINT investigations."""

    def __init__(self, config: Config):
        """
        Initialize the summarizer with the provided configuration.

        Args:
            config: The configuration to use for summarization.
        """
        self.config = config

    async def generate_summary(self, investigation: dict) -> str:
        """
        Generate an executive summary of the investigation.

        Args:
            investigation: The investigation to summarize.

        Returns:
            The executive summary as a string.
        """
        if self.config.has_api_key("openai_api_key"):
            return await self._generate_ai_summary(investigation)
        return self._generate_heuristic_summary(investigation)

    async def _generate_ai_summary(self, investigation: dict) -> str:
        """
        Generate an AI-powered executive summary.

        Args:
            investigation: The investigation to summarize.

        Returns:
            The AI-powered executive summary as a string.
        """
        try:
            import openai

            client = openai.AsyncOpenAI(api_key=self.config.openai_api_key)

            findings_brief = self._extract_key_findings(
                investigation.get("findings", {})
            )

            prompt = self._create_prompt(investigation, findings_brief)

            response = await client.chat.completions.create(
                model=self.config.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional intelligence analyst writing executive summaries. Be concise, factual, and objective.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=1000,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            return (
                self._generate_heuristic_summary(investigation)
                + f"\n\n[AI summary unavailable: {e}]"
            )

    def _generate_heuristic_summary(self, investigation: dict) -> str:
        """
        Generate a basic summary from findings data.

        Args:
            investigation: The investigation to summarize.

        Returns:
            The basic summary as a string.
        """
        target = investigation.get("target", "Unknown")
        input_type = investigation.get("input_type", "unknown")
        findings = investigation.get("findings", {})
        risk_score = investigation.get("risk_score", 0)

        sections = [f"Investigation of {input_type} target: {target}"]

        # Count findings
        total_profiles = 0
        total_breaches = 0
        modules_with_data = 0

        for module, data in findings.items():
            if isinstance(data, dict) and "error" not in data:
                modules_with_data += 1
                profiles = data.get("profiles", [])
                if isinstance(profiles, list):
                    total_profiles += len(profiles)
                breaches = data.get("breaches", {})
                if isinstance(breaches, dict):
                    total_breaches += breaches.get("total", 0)

        sections.append(
            f"Data collected from {modules_with_data} intelligence modules. "
            f"Found {total_profiles} associated online profiles."
        )

        if total_breaches:
            sections.append(
                f"Target appears in {total_breaches} known data breaches, indicating potential credential exposure."
            )

        risk_level = (
            "LOW" if risk_score < 0.4 else "MEDIUM" if risk_score < 0.7 else "HIGH"
        )
        sections.append(
            f"Overall risk assessment: {risk_level} (score: {risk_score:.1%})"
        )

        if investigation.get("errors"):
            sections.append(
                f"Note: {len(investigation['errors'])} module(s) encountered errors during collection."
            )

        return "\n\n".join(sections)

    def _extract_key_findings(self, findings: dict) -> dict:
        """
        Extract key findings from the provided findings data.

        Args:
            findings: The findings data to extract key findings from.

        Returns:
            A dictionary containing the key findings.
        """
        findings_brief = {}
        for module, data in findings.items():
            if isinstance(data, dict) and "error" not in data:
                brief = {}
                for k, v in data.items():
                    if k in (
                        "profiles",
                        "found_count",
                        "breaches",
                        "total",
                        "domain",
                        "username",
                        "email",
                    ):
                        if isinstance(v, list) and len(v) > 5:
                            brief[k] = f"{len(v)} items"
                        else:
                            brief[k] = v
                findings_brief[module] = brief
        return findings_brief

    def _create_prompt(self, investigation: dict, findings_brief: dict) -> str:
        """
        Create a prompt for the AI model.

        Args:
            investigation: The investigation to summarize.
            findings_brief: The key findings to include in the prompt.

        Returns:
            The prompt as a string.
        """
        return f"""Write a concise executive summary (3-5 paragraphs) of this OSINT investigation.

Target: {investigation.get('target')}
Type: {investigation.get('input_type')}
Risk Score: {investigation.get('risk_score', 'N/A')}

Key Findings:
{json.dumps(findings_brief, indent=2, default=str)[:5000]}

AI Analysis:
{json.dumps(investigation.get('ai_analysis', {}), indent=2, default=str)[:3000]}

Write in a professional, objective tone suitable for a security report. Include:
1. Overview of the investigation scope
2. Key findings and their significance
3. Risk assessment summary
4. Notable connections or patterns
5. Recommendations"""
