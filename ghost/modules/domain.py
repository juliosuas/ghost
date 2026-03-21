"""Domain/website OSINT — WHOIS, DNS, subdomains, tech stack, SSL, Wayback."""

import asyncio
import json
import ssl
import socket
from datetime import datetime
from typing import Any

import aiohttp
import dns.resolver

from ghost.core.config import Config


class DomainModule:
    """Comprehensive domain intelligence gathering."""

    def __init__(self, config: Config):
        self.config = config
        self.timeout = aiohttp.ClientTimeout(total=config.request_timeout)

    async def run(self, target: str, input_type: str = "domain") -> dict[str, Any]:
        """Run all domain OSINT checks."""
        domain = target.strip().lower()
        domain = domain.replace("http://", "").replace("https://", "").split("/")[0]

        results = await asyncio.gather(
            self._whois_lookup(domain),
            self._dns_records(domain),
            self._subdomain_enum(domain),
            self._tech_stack(domain),
            self._ssl_info(domain),
            self._wayback_history(domain),
            return_exceptions=True,
        )

        keys = ["whois", "dns", "subdomains", "tech_stack", "ssl", "wayback"]
        data = {}
        for key, result in zip(keys, results):
            data[key] = result if not isinstance(result, Exception) else {"error": str(result)}

        data["domain"] = domain
        return data

    async def _whois_lookup(self, domain: str) -> dict:
        """Get WHOIS information."""
        try:
            import whois
            w = whois.whois(domain)
            return {
                "registrar": w.registrar,
                "creation_date": str(w.creation_date) if w.creation_date else None,
                "expiration_date": str(w.expiration_date) if w.expiration_date else None,
                "updated_date": str(w.updated_date) if w.updated_date else None,
                "name_servers": list(w.name_servers) if w.name_servers else [],
                "registrant": w.org or w.name,
                "country": w.country,
                "state": w.state,
                "emails": list(w.emails) if w.emails else [],
                "dnssec": w.dnssec if hasattr(w, "dnssec") else None,
            }
        except Exception as e:
            return {"error": str(e)}

    async def _dns_records(self, domain: str) -> dict:
        """Enumerate DNS records."""
        records = {}
        record_types = ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "SRV"]

        for rtype in record_types:
            try:
                answers = dns.resolver.resolve(domain, rtype)
                records[rtype] = [str(r) for r in answers]
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
                pass
            except Exception:
                pass

        return records

    async def _subdomain_enum(self, domain: str) -> dict:
        """Enumerate subdomains using various techniques."""
        subdomains = set()

        # crt.sh - Certificate Transparency logs
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                url = f"https://crt.sh/?q=%.{domain}&output=json"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for entry in data:
                            name = entry.get("name_value", "")
                            for sub in name.split("\n"):
                                sub = sub.strip().lower()
                                if sub.endswith(domain) and "*" not in sub:
                                    subdomains.add(sub)
        except Exception:
            pass

        # Common subdomain brute-force list
        common = [
            "www", "mail", "ftp", "admin", "api", "dev", "staging", "test",
            "blog", "shop", "store", "app", "portal", "secure", "vpn",
            "remote", "webmail", "ns1", "ns2", "cdn", "media", "static",
            "docs", "help", "support", "status", "m", "mobile",
        ]

        for sub in common:
            full = f"{sub}.{domain}"
            try:
                dns.resolver.resolve(full, "A")
                subdomains.add(full)
            except Exception:
                pass

        return {
            "subdomains": sorted(subdomains),
            "count": len(subdomains),
        }

    async def _tech_stack(self, domain: str) -> dict:
        """Detect technology stack via headers and content analysis."""
        tech = {
            "server": None,
            "framework": [],
            "cms": None,
            "cdn": None,
            "analytics": [],
            "headers": {},
        }

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                url = f"https://{domain}"
                headers = {"User-Agent": self.config.user_agent}
                async with session.get(url, headers=headers, allow_redirects=True) as resp:
                    # Analyze headers
                    resp_headers = dict(resp.headers)
                    tech["headers"] = {
                        k: v for k, v in resp_headers.items()
                        if k.lower() in (
                            "server", "x-powered-by", "x-generator", "x-aspnet-version",
                            "x-frame-options", "content-security-policy", "strict-transport-security",
                        )
                    }

                    tech["server"] = resp_headers.get("Server")

                    powered_by = resp_headers.get("X-Powered-By", "")
                    if powered_by:
                        tech["framework"].append(powered_by)

                    # Analyze content
                    text = await resp.text()

                    # CMS detection
                    cms_signatures = {
                        "WordPress": ["wp-content", "wp-includes", "wordpress"],
                        "Drupal": ["drupal", "sites/default"],
                        "Joomla": ["joomla", "/administrator"],
                        "Shopify": ["shopify", "cdn.shopify.com"],
                        "Wix": ["wix.com", "wixstatic"],
                        "Squarespace": ["squarespace"],
                        "Ghost": ["ghost.org", "ghost-"],
                        "Hugo": ["hugo", "gohugo"],
                        "Next.js": ["__next", "_next"],
                        "Nuxt": ["__nuxt", "_nuxt"],
                    }

                    text_lower = text.lower()
                    for cms, signatures in cms_signatures.items():
                        if any(sig in text_lower for sig in signatures):
                            tech["cms"] = cms
                            break

                    # CDN detection
                    cdn_headers = {
                        "cloudflare": "Cloudflare",
                        "akamai": "Akamai",
                        "fastly": "Fastly",
                        "cloudfront": "CloudFront",
                        "stackpath": "StackPath",
                    }
                    for sig, name in cdn_headers.items():
                        if sig in str(resp_headers).lower() or sig in text_lower:
                            tech["cdn"] = name
                            break

                    # Analytics detection
                    analytics_signatures = {
                        "Google Analytics": ["google-analytics.com", "gtag", "ga("],
                        "Google Tag Manager": ["googletagmanager.com"],
                        "Facebook Pixel": ["facebook.com/tr", "fbq("],
                        "Hotjar": ["hotjar.com"],
                        "Mixpanel": ["mixpanel.com"],
                        "Segment": ["segment.com/analytics"],
                    }
                    for name, sigs in analytics_signatures.items():
                        if any(sig in text_lower for sig in sigs):
                            tech["analytics"].append(name)

        except Exception as e:
            tech["error"] = str(e)

        return tech

    async def _ssl_info(self, domain: str) -> dict:
        """Get SSL certificate information."""
        try:
            ctx = ssl.create_default_context()
            conn = ctx.wrap_socket(socket.socket(), server_hostname=domain)
            conn.settimeout(10)
            conn.connect((domain, 443))
            cert = conn.getpeercert()
            conn.close()

            subject = dict(x[0] for x in cert.get("subject", ()))
            issuer = dict(x[0] for x in cert.get("issuer", ()))
            san = [entry[1] for entry in cert.get("subjectAltName", ())]

            return {
                "subject": subject,
                "issuer": issuer,
                "version": cert.get("version"),
                "serial_number": cert.get("serialNumber"),
                "not_before": cert.get("notBefore"),
                "not_after": cert.get("notAfter"),
                "san": san,
                "ocsp": cert.get("OCSP", []),
            }
        except Exception as e:
            return {"error": str(e)}

    async def _wayback_history(self, domain: str) -> dict:
        """Check Wayback Machine history."""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # Get availability
                url = f"https://archive.org/wayback/available?url={domain}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        snapshot = data.get("archived_snapshots", {}).get("closest", {})

                # Get calendar data (number of captures)
                cdx_url = f"https://web.archive.org/cdx/search/cdx?url={domain}&output=json&limit=1&fl=timestamp"
                first_capture = None
                async with session.get(cdx_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if len(data) > 1:
                            first_capture = data[1][0]

                return {
                    "available": bool(snapshot),
                    "latest_snapshot": snapshot.get("url"),
                    "latest_timestamp": snapshot.get("timestamp"),
                    "first_capture": first_capture,
                }
        except Exception as e:
            return {"error": str(e)}
