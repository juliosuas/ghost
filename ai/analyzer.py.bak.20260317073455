"""LLM-powered analysis — profile building, risk assessment, behavior patterns."""

import json
from typing import Any, Dict, List, Optional

from ghost.core.config import Config


class AIAnalyzer:
    """AI-powered analysis of OSINT findings."""

    def __init__(self, config: Config):
        """Initialize AIAnalyzer with configuration."""
        self.config = config

    async def analyze(
        self,
        target: str,
        input_type: str,
        findings: Dict[str, Any],
        correlations: Dict,
    ) -> Dict:
        """
        Run comprehensive AI analysis on investigation data.

        Args:
            target: Target entity for analysis.
            input_type: Type of input data.
            findings: Investigation findings.
            correlations: Correlations between findings.

        Returns:
            AI analysis results or fallback analysis if AI is not available.
        """
        if not self.config.has_api_key("openai_api_key"):
            return self._fallback_analysis(findings)

        try:
            import openai

            client = openai.AsyncOpenAI(api_key=self.config.openai_api_key)

            # Prepare findings summary (truncated for token limits)
            findings_text = self._sanitize_findings(findings)[:10000]
            correlations_text = json.dumps(correlations, indent=2, default=str)[:3000]

            prompt = f"""You are an expert OSINT analyst. Analyze the following investigation data for target "{target}" (type: {input_type}).

## Findings
{findings_text}

## Correlations
{correlations_text}

Provide a comprehensive analysis in JSON format with these keys:

1. "profile" — Object with: likely_name, estimated_age_range, likely_location, occupation_hints, interests, personality_traits, online_behavior_pattern
2. "risk_assessment" — Object with: risk_score (0.0-1.0), risk_level (low/medium/high/critical), risk_factors (list of strings), recommendations (list)
3. "connections" — List of identified connections between data points with confidence scores
4. "timeline" — Key events in chronological order
5. "sentiment" — Overall online presence sentiment analysis (positive/neutral/negative with explanation)
6. "digital_footprint" — Assessment of digital exposure level and privacy posture
7. "key_findings" — Top 5 most significant findings
8. "confidence" — Overall confidence in analysis (0.0-1.0) with explanation

Be objective, factual, and note uncertainty where applicable. Do not make unsupported claims."""

            response = await client.chat.completions.create(
                model=self.config.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional OSINT analyst. Provide objective, evidence-based analysis. Always respond with valid JSON. Flag low-confidence assessments explicitly.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=3000,
            )

            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]

            analysis = json.loads(content)

            # Ensure risk_score exists
            risk = analysis.get("risk_assessment", {})
            analysis["risk_score"] = risk.get("risk_score", 0.3)

            return analysis

        except json.JSONDecodeError as e:
            # Handle JSON decoding errors explicitly
            return {"error": "AI returned invalid JSON", "raw_response": content[:500]}
        except Exception as e:
            # Handle other exceptions explicitly
            return {"error": f"AI analysis failed: {e}"}

    def _sanitize_findings(self, findings: Dict[str, Any]) -> Dict:
        """
        Remove large/binary data and limit size for AI processing.

        Args:
            findings: Investigation findings.

        Returns:
            Sanitized findings for AI analysis.
        """
        sanitized = {}
        for module, data in findings.items():
            if isinstance(data, dict):
                sanitized[module] = {
                    k: v
                    for k, v in data.items()
                    if k not in ("raw", "encoding", "all_tags", "html")
                    and not isinstance(v, bytes)
                }
                # Truncate long lists
                for k, v in sanitized[module].items():
                    if isinstance(v, list) and len(v) > 20:
                        sanitized[module][k] = v[:20] + [f"... and {len(v) - 20} more"]
            else:
                sanitized[module] = str(data)[:500]
        return sanitized

    def _fallback_analysis(self, findings: Dict[str, Any]) -> Dict:
        """
        Basic heuristic analysis when AI is not available.

        Args:
            findings: Investigation findings.

        Returns:
            Fallback analysis results.
        """
        profile_count = 0
        breach_count = 0
        locations = set()

        for module, data in findings.items():
            if not isinstance(data, dict) or "error" in data:
                continue

            profiles = data.get("profiles", [])
            if isinstance(profiles, list):
                profile_count += len(profiles)

            breaches = data.get("breaches", {})
            if isinstance(breaches, dict):
                breach_count += breaches.get("total", 0)
            elif isinstance(breaches, list):
                breach_count += len(breaches)

            for key in ("location", "city", "country"):
                val = data.get(key)
                if val and isinstance(val, str):
                    locations.add(val)

        # Simple risk scoring
        risk_score = min(
            1.0,
            (
                (0.1 if profile_count > 5 else 0)
                + (0.2 if profile_count > 15 else 0)
                + (0.3 if breach_count > 0 else 0)
                + (0.2 if breach_count > 5 else 0)
                + 0.1  # Base risk for any digital presence
            ),
        )

        risk_level = (
            "low" if risk_score < 0.4 else "medium" if risk_score < 0.7 else "high"
        )

        return {
            "risk_score": risk_score,
            "risk_assessment": {
                "risk_score": risk_score,
                "risk_level": risk_level,
                "risk_factors": [
                    f"Found on {profile_count} platforms",
                    (
                        f"Involved in {breach_count} data breaches"
                        if breach_count
                        else "No known breaches"
                    ),
                    (
                        f"Location data found: {', '.join(locations)}"
                        if locations
                        else "No location data found"
                    ),
                ],
            },
            "digital_footprint": {
                "platform_count": profile_count,
                "breach_exposure": breach_count,
                "locations_found": list(locations),
            },
            "note": "Basic analysis — configure OPENAI_API_KEY for AI-powered insights",
        }
