"""Email OSINT — breach checks, validation, account discovery, domain info."""

import asyncio
import re
import aiohttp
from typing import Any

from ghost.core.config import Config


class EmailModule:
    """Comprehensive email intelligence gathering."""

    def __init__(self, config: Config):
        self.config = config
        self.timeout = aiohttp.ClientTimeout(total=config.request_timeout)

    async def run(self, target: str, input_type: str = "email") -> dict[str, Any]:
        """Run all email OSINT checks."""
        email = target.strip().lower()

        results = await asyncio.gather(
            self._validate_email(email),
            self._check_breaches(email),
            self._discover_accounts(email),
            self._domain_info(email),
            self._gravatar_check(email),
            return_exceptions=True,
        )

        return {
            "email": email,
            "validation": results[0] if not isinstance(results[0], Exception) else {"error": str(results[0])},
            "breaches": results[1] if not isinstance(results[1], Exception) else {"error": str(results[1])},
            "accounts": results[2] if not isinstance(results[2], Exception) else {"error": str(results[2])},
            "domain": results[3] if not isinstance(results[3], Exception) else {"error": str(results[3])},
            "gravatar": results[4] if not isinstance(results[4], Exception) else {"error": str(results[4])},
        }

    async def _validate_email(self, email: str) -> dict:
        """Validate email format and check MX records."""
        # Format check
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        is_valid_format = bool(re.match(pattern, email))

        domain = email.split("@")[1]

        # MX record check
        mx_records = []
        try:
            import dns.resolver
            answers = dns.resolver.resolve(domain, "MX")
            mx_records = [
                {"priority": r.preference, "host": str(r.exchange).rstrip(".")}
                for r in answers
            ]
        except Exception:
            pass

        # Common provider detection
        provider = self._detect_provider(domain)

        return {
            "valid_format": is_valid_format,
            "domain": domain,
            "mx_records": mx_records,
            "has_mx": len(mx_records) > 0,
            "provider": provider,
            "disposable": self._is_disposable(domain),
        }

    async def _check_breaches(self, email: str) -> dict:
        """Check email against breach databases."""
        breaches = []

        # HIBP API
        if self.config.has_api_key("hibp_api_key"):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    headers = {
                        "hibp-api-key": self.config.hibp_api_key,
                        "User-Agent": "Ghost-OSINT-Platform",
                    }
                    url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
                    async with session.get(url, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            breaches = [
                                {
                                    "name": b.get("Name"),
                                    "date": b.get("BreachDate"),
                                    "data_classes": b.get("DataClasses", []),
                                    "verified": b.get("IsVerified", False),
                                    "description": b.get("Description", ""),
                                }
                                for b in data
                            ]
                        elif resp.status == 404:
                            pass  # No breaches found
            except Exception as e:
                return {"error": str(e), "breaches": []}

        return {
            "total": len(breaches),
            "breaches": breaches,
            "api_available": self.config.has_api_key("hibp_api_key"),
        }

    async def _discover_accounts(self, email: str) -> dict:
        """Discover accounts associated with an email."""
        accounts = []

        # Check common services for account existence via password reset / signup
        services = [
            ("Twitter/X", "https://api.twitter.com/i/users/email_available.json?email={}"),
            ("Spotify", "https://spclient.wg.spotify.com/signup/public/v1/account?validate=1&email={}"),
        ]

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            for name, url in services:
                try:
                    headers = {"User-Agent": self.config.user_agent}
                    async with session.get(url.format(email), headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            # Each API has different response structure
                            accounts.append({
                                "service": name,
                                "exists": True,
                                "response_code": resp.status,
                            })
                except Exception:
                    pass

        # Hunter.io for professional email discovery
        if self.config.has_api_key("hunter_api_key"):
            try:
                domain = email.split("@")[1]
                url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={self.config.hunter_api_key}"
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            emails = data.get("data", {}).get("emails", [])
                            accounts.append({
                                "service": "Hunter.io",
                                "related_emails": [
                                    {"email": e["value"], "type": e.get("type")}
                                    for e in emails[:10]
                                ],
                            })
            except Exception:
                pass

        return {"accounts": accounts, "count": len(accounts)}

    async def _domain_info(self, email: str) -> dict:
        """Get domain WHOIS information for the email domain."""
        domain = email.split("@")[1]
        info = {"domain": domain}

        try:
            import whois
            w = whois.whois(domain)
            info.update({
                "registrar": w.registrar,
                "creation_date": str(w.creation_date) if w.creation_date else None,
                "expiration_date": str(w.expiration_date) if w.expiration_date else None,
                "name_servers": w.name_servers if w.name_servers else [],
                "org": w.org,
                "country": w.country,
            })
        except Exception as e:
            info["whois_error"] = str(e)

        return info

    async def _gravatar_check(self, email: str) -> dict:
        """Check for Gravatar profile."""
        import hashlib
        email_hash = hashlib.md5(email.strip().lower().encode()).hexdigest()
        profile_url = f"https://en.gravatar.com/{email_hash}.json"
        avatar_url = f"https://www.gravatar.com/avatar/{email_hash}"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(profile_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        entry = data.get("entry", [{}])[0]
                        return {
                            "exists": True,
                            "display_name": entry.get("displayName"),
                            "profile_url": entry.get("profileUrl"),
                            "avatar_url": avatar_url,
                            "about": entry.get("aboutMe"),
                            "location": entry.get("currentLocation"),
                            "accounts": [
                                {"service": a.get("shortname"), "url": a.get("url")}
                                for a in entry.get("accounts", [])
                            ],
                        }
                    return {"exists": False, "avatar_url": avatar_url + "?d=404"}
        except Exception as e:
            return {"error": str(e)}

    def _detect_provider(self, domain: str) -> str:
        providers = {
            "gmail.com": "Google",
            "googlemail.com": "Google",
            "outlook.com": "Microsoft",
            "hotmail.com": "Microsoft",
            "live.com": "Microsoft",
            "yahoo.com": "Yahoo",
            "icloud.com": "Apple",
            "me.com": "Apple",
            "protonmail.com": "ProtonMail",
            "proton.me": "ProtonMail",
            "tutanota.com": "Tutanota",
            "aol.com": "AOL",
            "zoho.com": "Zoho",
            "yandex.com": "Yandex",
            "mail.ru": "Mail.ru",
        }
        return providers.get(domain, "Custom/Corporate")

    def _is_disposable(self, domain: str) -> bool:
        disposable_domains = {
            "tempmail.com", "throwaway.email", "guerrillamail.com",
            "mailinator.com", "10minutemail.com", "trashmail.com",
            "yopmail.com", "sharklasers.com", "guerrillamailblock.com",
            "dispostable.com", "maildrop.cc", "temp-mail.org",
        }
        return domain in disposable_domains
