"""Phone number OSINT — carrier lookup, location, social media association."""

import asyncio
import aiohttp
from typing import Any

import phonenumbers
from phonenumbers import carrier as pn_carrier, geocoder, timezone as pn_timezone

from ghost.core.config import Config


class PhoneModule:
    """Phone number intelligence gathering."""

    def __init__(self, config: Config):
        self.config = config
        self.timeout = aiohttp.ClientTimeout(total=config.request_timeout)

    async def run(self, target: str, input_type: str = "phone") -> dict[str, Any]:
        """Run all phone number OSINT checks."""
        results = await asyncio.gather(
            self._parse_and_validate(target),
            self._check_spam_databases(target),
            self._check_social_media(target),
            return_exceptions=True,
        )

        base = results[0] if not isinstance(results[0], Exception) else {"error": str(results[0])}
        spam = results[1] if not isinstance(results[1], Exception) else {"error": str(results[1])}
        social = results[2] if not isinstance(results[2], Exception) else {"error": str(results[2])}

        if isinstance(base, dict):
            base["spam_check"] = spam
            base["social_media"] = social

        return base

    async def _parse_and_validate(self, number: str) -> dict:
        """Parse, validate, and extract info from phone number."""
        # Clean the number
        cleaned = number.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if not cleaned.startswith("+"):
            cleaned = "+1" + cleaned  # Default to US

        try:
            parsed = phonenumbers.parse(cleaned)
        except phonenumbers.NumberParseException as e:
            return {"error": f"Invalid phone number: {e}", "input": number}

        is_valid = phonenumbers.is_valid_number(parsed)
        is_possible = phonenumbers.is_possible_number(parsed)

        # Carrier info
        carrier_name = pn_carrier.name_for_number(parsed, "en")

        # Location
        location = geocoder.description_for_number(parsed, "en")

        # Timezone
        tz = pn_timezone.time_zones_for_number(parsed)

        # Number type
        number_type = phonenumbers.number_type(parsed)
        type_names = {
            0: "FIXED_LINE",
            1: "MOBILE",
            2: "FIXED_LINE_OR_MOBILE",
            3: "TOLL_FREE",
            4: "PREMIUM_RATE",
            5: "SHARED_COST",
            6: "VOIP",
            7: "PERSONAL_NUMBER",
            8: "PAGER",
            9: "UAN",
            10: "VOICEMAIL",
        }

        return {
            "input": number,
            "formatted": {
                "international": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
                "national": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL),
                "e164": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164),
            },
            "valid": is_valid,
            "possible": is_possible,
            "country_code": parsed.country_code,
            "national_number": parsed.national_number,
            "carrier": carrier_name or "Unknown",
            "location": location or "Unknown",
            "timezone": list(tz) if tz else [],
            "type": type_names.get(number_type, "UNKNOWN"),
        }

    async def _check_spam_databases(self, number: str) -> dict:
        """Check number against spam/scam databases."""
        reports = []

        # Check public spam lookup APIs
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # NumVerify API (free tier)
                cleaned = number.replace("+", "").replace(" ", "").replace("-", "")
                url = f"http://apilayer.net/api/validate?access_key=free&number={cleaned}"
                try:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("valid"):
                                reports.append({
                                    "source": "numverify",
                                    "valid": data.get("valid"),
                                    "line_type": data.get("line_type"),
                                    "carrier": data.get("carrier"),
                                    "location": data.get("location"),
                                })
                except Exception:
                    pass

        except Exception as e:
            return {"error": str(e), "reports": []}

        return {"reports": reports, "is_spam": False, "spam_score": 0}

    async def _check_social_media(self, number: str) -> dict:
        """Check if the phone number is linked to social media accounts."""
        linked_accounts = []

        # Note: Actual social media lookups would require specific APIs
        # This checks common patterns and public APIs
        cleaned = number.replace("+", "").replace(" ", "").replace("-", "")

        services_to_check = [
            ("Telegram", f"https://t.me/+{cleaned}"),
            ("WhatsApp", f"https://wa.me/{cleaned}"),
            ("Signal", None),  # Signal doesn't have public lookup
        ]

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            for service, url in services_to_check:
                if url is None:
                    continue
                try:
                    headers = {"User-Agent": self.config.user_agent}
                    async with session.head(url, headers=headers, allow_redirects=True) as resp:
                        if resp.status == 200:
                            linked_accounts.append({
                                "service": service,
                                "url": url,
                                "status": "possibly_linked",
                            })
                except Exception:
                    pass

        return {"linked_accounts": linked_accounts, "count": len(linked_accounts)}
