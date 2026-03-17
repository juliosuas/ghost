"""Dark web monitoring — Ahmia search, breach databases, paste sites."""

import asyncio
import aiohttp
from typing import Any

from ghost.core.config import Config


class DarkWebModule:
    """Dark web and underground intelligence gathering."""

    def __init__(self, config: Config):
        """
        Initialize the DarkWebModule.

        :param config: The configuration object.
        """
        self.config = config
        self.timeout = aiohttp.ClientTimeout(total=config.request_timeout)

    async def run(self, target: str, input_type: str = "username") -> dict[str, Any]:
        """
        Run dark web monitoring checks.

        :param target: The target to search for.
        :param input_type: The type of input (default: "username").
        :return: A dictionary containing the results of the checks.
        """
        results = await asyncio.gather(
            self._search_ahmia(target),
            self._check_breach_databases(target),
            self._check_paste_sites(target),
            self._check_dehashed(target),
            return_exceptions=True,
        )

        keys = ["ahmia", "breaches", "pastes", "dehashed"]
        data = {"target": target, "input_type": input_type}
        for key, result in zip(keys, results):
            data[key] = (
                result if not isinstance(result, Exception) else {"error": str(result)}
            )

        return data

    async def _search_ahmia(self, query: str) -> dict:
        """
        Search Ahmia.fi — clearnet search engine for Tor hidden services.

        :param query: The query to search for.
        :return: A dictionary containing the search results.
        """
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                url = f"https://ahmia.fi/search/?q={query}"
                headers = {"User-Agent": self.config.user_agent}
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        # Parse results from HTML
                        from bs4 import BeautifulSoup

                        soup = BeautifulSoup(text, "html.parser")
                        results = []
                        for item in soup.select("li.result"):
                            title_el = item.select_one("h4")
                            link_el = item.select_one("a")
                            desc_el = item.select_one("p")
                            if title_el and link_el:
                                results.append(
                                    {
                                        "title": title_el.get_text(strip=True),
                                        "url": link_el.get("href", ""),
                                        "description": (
                                            desc_el.get_text(strip=True)
                                            if desc_el
                                            else ""
                                        ),
                                    }
                                )
                        return {"results": results[:20], "count": len(results)}
                    return {"results": [], "error": f"Status {resp.status}"}
        except Exception as e:
            return {"results": [], "error": str(e)}

    async def _check_breach_databases(self, target: str) -> dict:
        """
        Check against known breach compilation databases.

        :param target: The target to search for.
        :return: A dictionary containing the breach data.
        """
        breaches = []

        # HIBP check
        if self.config.has_api_key("hibp_api_key"):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    # Check breaches
                    if "@" in target:
                        url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{target}"
                    else:
                        url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{target}?truncateResponse=false"

                    headers = {
                        "hibp-api-key": self.config.hibp_api_key,
                        "User-Agent": "Ghost-OSINT-Platform",
                    }
                    async with session.get(url, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            for breach in data:
                                breaches.append(
                                    {
                                        "name": breach.get("Name"),
                                        "title": breach.get("Title"),
                                        "date": breach.get("BreachDate"),
                                        "pwn_count": breach.get("PwnCount"),
                                        "data_classes": breach.get("DataClasses", []),
                                        "verified": breach.get("IsVerified"),
                                    }
                                )

                    # Check pastes
                    if "@" in target:
                        paste_url = (
                            f"https://haveibeenpwned.com/api/v3/pasteaccount/{target}"
                        )
                        async with session.get(paste_url, headers=headers) as resp:
                            if resp.status == 200:
                                pastes = await resp.json()
                                return {
                                    "breaches": breaches,
                                    "pastes_from_hibp": [
                                        {
                                            "source": p.get("Source"),
                                            "title": p.get("Title"),
                                            "date": p.get("Date"),
                                            "email_count": p.get("EmailCount"),
                                        }
                                        for p in pastes
                                    ],
                                    "total_breaches": len(breaches),
                                }
            except Exception as e:
                return {"error": str(e), "breaches": []}

        return {
            "breaches": breaches,
            "total_breaches": len(breaches),
            "api_available": self.config.has_api_key("hibp_api_key"),
        }

    async def _check_paste_sites(self, target: str) -> dict:
        """
        Monitor paste sites for mentions of the target.

        :param target: The target to search for.
        :return: A dictionary containing the paste data.
        """
        pastes = []

        # Search public paste indices
        paste_searches = [
            ("PasteBin (Google)", f'site:pastebin.com "{target}"'),
            ("GitHub Gists", f'site:gist.github.com "{target}"'),
            ("Ghostbin", f'site:ghostbin.com "{target}"'),
        ]

        # Use Google Custom Search if available
        if self.config.has_api_key("google_api_key") and self.config.has_api_key(
            "google_cx"
        ):
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                for name, query in paste_searches:
                    try:
                        url = (
                            f"https://www.googleapis.com/customsearch/v1"
                            f"?key={self.config.google_api_key}"
                            f"&cx={self.config.google_cx}"
                            f"&q={query}"
                        )
                        async with session.get(url) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                for item in data.get("items", [])[:5]:
                                    pastes.append(
                                        {
                                            "source": name,
                                            "title": item.get("title"),
                                            "url": item.get("link"),
                                            "snippet": item.get("snippet"),
                                        }
                                    )
                    except Exception:
                        pass

        return {"pastes": pastes, "count": len(pastes)}

    async def _check_dehashed(self, target: str) -> dict:
        """
        Check DeHashed API for breach data (if configured).

        :param target: The target to search for.
        :return: A dictionary containing the DeHashed data.
        """
        # DeHashed requires paid API access
        return {
            "available": False,
            "note": "DeHashed integration requires API credentials",
        }
