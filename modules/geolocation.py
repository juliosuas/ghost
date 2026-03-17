"""IP/location intelligence — IP geolocation, address lookup, nearby entities."""

import asyncio
import socket
import aiohttp
from typing import Any, Dict, Optional

from ghost.core.config import Config


class GeolocationModule:
    """Geolocation and IP intelligence."""

    def __init__(self, config: Config):
        """Initialize the geolocation module with the provided configuration."""
        self.config = config
        self.timeout = aiohttp.ClientTimeout(total=config.request_timeout)

    async def run(self, target: str, input_type: str = "domain") -> Dict[str, Any]:
        """Run geolocation intelligence gathering.

        Args:
            target: The target to gather geolocation data for.
            input_type: The type of the input (default: "domain").

        Returns:
            A dictionary containing the gathered geolocation data.
        """
        # Resolve domain to IP if needed
        ip = await self._resolve_to_ip(target)

        # Gather geolocation data using IP geolocation and Shodan
        results = await asyncio.gather(
            self._ip_geolocation(ip) if ip else self._create_error_result("No IP"),
            self._shodan_lookup(ip) if ip else self._create_error_result("No IP"),
            return_exceptions=True,
        )

        # Consolidate and return the results
        return {
            "target": target,
            "resolved_ip": ip,
            "geolocation": (
                results[0]
                if not isinstance(results[0], Exception)
                else self._create_error_result(str(results[0]))
            ),
            "shodan": (
                results[1]
                if not isinstance(results[1], Exception)
                else self._create_error_result(str(results[1]))
            ),
        }

    async def _resolve_to_ip(self, target: str) -> Optional[str]:
        """Resolve a hostname/domain to IP address.

        Args:
            target: The hostname or domain to resolve.

        Returns:
            The resolved IP address or None if resolution fails.
        """
        target = target.replace("http://", "").replace("https://", "").split("/")[0]

        # Check if already an IP
        try:
            socket.inet_aton(target)
            return target
        except socket.error:
            pass

        try:
            return socket.gethostbyname(target)
        except socket.gaierror:
            return None

    async def _ip_geolocation(self, ip: str) -> Dict[str, Any]:
        """Get geolocation data for an IP address.

        Args:
            ip: The IP address to get geolocation data for.

        Returns:
            A dictionary containing the geolocation data.
        """
        results = {}

        # IPInfo.io
        if self.config.has_api_key("ipinfo_token"):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    url = f"https://ipinfo.io/{ip}?token={self.config.ipinfo_token}"
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            results["ipinfo"] = {
                                "ip": data.get("ip"),
                                "city": data.get("city"),
                                "region": data.get("region"),
                                "country": data.get("country"),
                                "location": data.get("loc"),
                                "org": data.get("org"),
                                "postal": data.get("postal"),
                                "timezone": data.get("timezone"),
                                "hostname": data.get("hostname"),
                            }
            except Exception as e:
                results["ipinfo"] = {"error": str(e)}

        # Free fallback: ip-api.com
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                url = f"http://ip-api.com/json/{ip}?fields=status,message,continent,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,asname,mobile,proxy,hosting,query"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("status") == "success":
                            results["ip_api"] = {
                                "ip": data.get("query"),
                                "continent": data.get("continent"),
                                "country": data.get("country"),
                                "country_code": data.get("countryCode"),
                                "region": data.get("regionName"),
                                "city": data.get("city"),
                                "zip": data.get("zip"),
                                "latitude": data.get("lat"),
                                "longitude": data.get("lon"),
                                "timezone": data.get("timezone"),
                                "isp": data.get("isp"),
                                "org": data.get("org"),
                                "as": data.get("as"),
                                "as_name": data.get("asname"),
                                "is_mobile": data.get("mobile"),
                                "is_proxy": data.get("proxy"),
                                "is_hosting": data.get("hosting"),
                            }
        except Exception as e:
            results["ip_api"] = {"error": str(e)}

        # Consolidate best data
        best = results.get("ipinfo", results.get("ip_api", {}))
        results["consolidated"] = {
            "ip": ip,
            "city": best.get("city"),
            "region": best.get("region") or best.get("regionName"),
            "country": best.get("country"),
            "latitude": best.get("latitude")
            or (
                best.get("location", ",").split(",")[0]
                if best.get("location")
                else None
            ),
            "longitude": best.get("longitude")
            or (
                best.get("location", ",").split(",")[1]
                if best.get("location")
                else None
            ),
            "isp": best.get("isp") or best.get("org"),
        }

        return results

    async def _shodan_lookup(self, ip: str) -> Dict[str, Any]:
        """Look up IP on Shodan for open ports and services.

        Args:
            ip: The IP address to look up on Shodan.

        Returns:
            A dictionary containing the Shodan lookup results.
        """
        if not self.config.has_api_key("shodan_api_key"):
            return {"available": False, "note": "Shodan API key not configured"}

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                url = f"https://api.shodan.io/shodan/host/{ip}?key={self.config.shodan_api_key}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            "available": True,
                            "ip": data.get("ip_str"),
                            "os": data.get("os"),
                            "ports": data.get("ports", []),
                            "hostnames": data.get("hostnames", []),
                            "org": data.get("org"),
                            "isp": data.get("isp"),
                            "vulns": data.get("vulns", []),
                            "last_update": data.get("last_update"),
                            "services": [
                                {
                                    "port": s.get("port"),
                                    "protocol": s.get("transport"),
                                    "product": s.get("product"),
                                    "version": s.get("version"),
                                    "banner": s.get("data", "")[:200],
                                }
                                for s in data.get("data", [])[:20]
                            ],
                        }
                    return {"available": True, "error": f"Status {resp.status}"}
        except Exception as e:
            return {"available": False, "error": str(e)}

    @staticmethod
    def _create_error_result(message: str) -> Dict[str, Any]:
        """Create a dictionary representing an error result.

        Args:
            message: The error message.

        Returns:
            A dictionary containing the error result.
        """
        return {"error": message}
