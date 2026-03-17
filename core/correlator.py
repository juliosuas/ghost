"""AI-powered correlation engine — finds connections between data points."""

import json
from typing import Any, Dict, List, Optional

from ghost.core.config import Config


class Correlator:
    """Correlates findings across modules using AI and heuristic analysis."""

    def __init__(self, config: Config):
        """Initialize the correlator with a configuration object."""
        self.config = config

    async def correlate(self, findings: Dict[str, Any]) -> Dict:
        """Analyze all findings and identify connections and patterns."""
        correlations = {
            "identities": self._correlate_identities(findings),
            "connections": self._find_connections(findings),
            "timeline": self._build_timeline(findings),
            "locations": self._correlate_locations(findings),
            "ai_insights": await self._ai_correlate(findings),
        }
        return correlations

    def _correlate_identities(self, findings: Dict) -> List[Dict]:
        """Find identity overlaps across platforms."""
        identities = []
        seen_names: Dict[str, List[str]] = {}
        seen_emails: Dict[str, List[str]] = {}

        for module, data in findings.items():
            if isinstance(data, dict) and "error" not in data:
                # Extract names
                for key in ("display_name", "name", "full_name", "username"):
                    val = data.get(key)
                    if val and isinstance(val, str):
                        seen_names.setdefault(val.lower(), []).append(module)

                # Extract emails
                for key in ("email", "emails"):
                    val = data.get(key)
                    if isinstance(val, str):
                        seen_emails.setdefault(val.lower(), []).append(module)
                    elif isinstance(val, list):
                        for e in val:
                            if isinstance(e, str):
                                seen_emails.setdefault(e.lower(), []).append(module)

                # Check profiles list
                profiles = data.get("profiles", [])
                if isinstance(profiles, list):
                    for profile in profiles:
                        if isinstance(profile, dict):
                            name = profile.get("name") or profile.get("username")
                            if name:
                                seen_names.setdefault(name.lower(), []).append(module)

        for name, sources in seen_names.items():
            if len(sources) > 1:
                identities.append(
                    {
                        "type": "name",
                        "value": name,
                        "sources": sources,
                        "confidence": min(0.9, 0.5 + 0.1 * len(sources)),
                    }
                )

        for email, sources in seen_emails.items():
            if len(sources) > 1:
                identities.append(
                    {
                        "type": "email",
                        "value": email,
                        "sources": sources,
                        "confidence": 0.95,
                    }
                )

        return identities

    def _find_connections(self, findings: Dict) -> List[Dict]:
        """Find connections between different data points."""
        connections = []
        all_usernames: Set[str] = set()
        all_domains: Set[str] = set()

        for module, data in findings.items():
            if not isinstance(data, dict) or "error" in data:
                continue

            # Collect usernames
            profiles = data.get("profiles", [])
            if isinstance(profiles, list):
                for p in profiles:
                    if isinstance(p, dict) and p.get("username"):
                        all_usernames.add(p["username"].lower())

            username = data.get("username")
            if username:
                all_usernames.add(username.lower())

            # Collect domains
            domain = data.get("domain")
            if domain:
                all_domains.add(domain.lower())

        # Cross-reference usernames appearing in multiple contexts
        for module, data in findings.items():
            if not isinstance(data, dict):
                continue
            profiles = data.get("profiles", [])
            if isinstance(profiles, list):
                for p in profiles:
                    if isinstance(p, dict):
                        url = p.get("url", "")
                        for uname in all_usernames:
                            if (
                                uname in url.lower()
                                and uname != p.get("username", "").lower()
                            ):
                                connections.append(
                                    {
                                        "type": "username_link",
                                        "from": uname,
                                        "to": p.get("platform", module),
                                        "evidence": url,
                                    }
                                )

        return connections

    def _build_timeline(self, findings: Dict) -> List[Dict]:
        """Extract and sort temporal events from findings."""
        events = []

        for module, data in findings.items():
            if not isinstance(data, dict) or "error" in data:
                continue

            # Account creation dates
            created = (
                data.get("created_at")
                or data.get("creation_date")
                or data.get("registered")
            )
            if created:
                events.append(
                    {
                        "date": str(created),
                        "event": f"Account/entity created on {module}",
                        "source": module,
                    }
                )

            # Breach dates
            breaches = data.get("breaches", [])
            if isinstance(breaches, list):
                for breach in breaches:
                    if isinstance(breach, dict) and breach.get("date"):
                        events.append(
                            {
                                "date": breach["date"],
                                "event": f"Data breach: {breach.get('name', 'Unknown')}",
                                "source": "darkweb",
                            }
                        )

            # Posts/activity
            last_active = data.get("last_active") or data.get("last_post")
            if last_active:
                events.append(
                    {
                        "date": str(last_active),
                        "event": f"Last activity on {module}",
                        "source": module,
                    }
                )

        events.sort(key=lambda x: x.get("date", ""))
        return events

    def _correlate_locations(self, findings: Dict) -> List[Dict]:
        """Find location data across findings."""
        locations = []

        for module, data in findings.items():
            if not isinstance(data, dict) or "error" in data:
                continue

            for key in ("location", "city", "country", "region", "geo"):
                val = data.get(key)
                if val and isinstance(val, str):
                    locations.append(
                        {
                            "value": val,
                            "source": module,
                            "field": key,
                        }
                    )

            # GPS coordinates
            lat = data.get("latitude") or data.get("lat")
            lon = data.get("longitude") or data.get("lon") or data.get("lng")
            if lat and lon:
                locations.append(
                    {
                        "value": f"{lat}, {lon}",
                        "lat": lat,
                        "lon": lon,
                        "source": module,
                        "field": "coordinates",
                    }
                )

        return locations

    async def _ai_correlate(self, findings: Dict) -> Dict:
        """Use LLM to find deeper correlations."""
        if not self.config.has_api_key("openai_api_key"):
            return {"note": "AI correlation unavailable — no API key configured"}

        try:
            import openai

            client = openai.AsyncOpenAI(api_key=self.config.openai_api_key)

            # Prepare a sanitized summary of findings for the LLM
            summary = {}
            for module, data in findings.items():
                if isinstance(data, dict) and "error" not in data:
                    summary[module] = {
                        k: v
                        for k, v in data.items()
                        if isinstance(v, (str, int, float, bool, list)) and k != "raw"
                    }

            prompt = f"""Analyze the following OSINT investigation findings and identify:
1. Hidden connections between data points
2. Patterns in behavior or activity
3. Potential aliases or linked identities
4. Notable risks or red flags
5. Confidence assessment of key findings

Findings:
{json.dumps(summary, indent=2, default=str)[:8000]}

Respond in JSON with keys: connections, patterns, aliases, risks, confidence_notes"""

            response = await client.chat.completions.create(
                model=self.config.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an OSINT analyst. Analyze data objectively and identify connections. Always respond with valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=2000,
            )

            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(content)
        except openai.error.InvalidRequestError as e:
            return {"error": f"Invalid AI request: {e}"}
        except openai.error.RateLimitError as e:
            return {"error": f"Rate limit exceeded: {e}"}
        except Exception as e:
            return {"error": f"AI correlation failed: {e}"}
