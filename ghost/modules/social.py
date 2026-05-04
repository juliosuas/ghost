"""Social media deep dive — profile analysis across major platforms."""

import asyncio
import aiohttp
from typing import Any

from ghost.core.config import Config


class SocialModule:
    """Deep social media intelligence gathering."""

    def __init__(self, config: Config):
        self.config = config
        self.timeout = aiohttp.ClientTimeout(total=config.request_timeout)

    async def run(self, target: str, input_type: str = "username") -> dict[str, Any]:
        """Run social media deep dive on target."""
        username = target.split("@")[-1] if "@" in target else target.strip()

        results = await asyncio.gather(
            self._check_instagram(username),
            self._check_twitter(username),
            self._check_reddit(username),
            self._check_tiktok(username),
            self._check_github(username),
            self._check_linkedin(username),
            return_exceptions=True,
        )

        platforms = {}
        names = [
            "instagram", "twitter", "reddit", "tiktok", "github", "linkedin"
        ]
        for name, result in zip(names, results):
            if isinstance(result, Exception):
                platforms[name] = {"error": str(result)}
            else:
                platforms[name] = result

        # Aggregate profile data
        profiles = []
        for name, data in platforms.items():
            if isinstance(data, dict) and data.get("found"):
                profiles.append({
                    "platform": name,
                    "username": data.get("username", username),
                    "url": data.get("url", ""),
                    "display_name": data.get("display_name", ""),
                    "bio": data.get("bio", ""),
                    "followers": data.get("followers"),
                    "following": data.get("following"),
                    "posts": data.get("posts"),
                    "verified": data.get("verified", False),
                    "created_at": data.get("created_at"),
                })

        return {
            "username": username,
            "platforms": platforms,
            "profiles": profiles,
            "total_found": len(profiles),
        }

    async def _check_instagram(self, username: str) -> dict:
        """Check Instagram profile."""
        url = f"https://www.instagram.com/{username}/"
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                headers = {"User-Agent": self.config.user_agent}
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        return {
                            "found": True,
                            "url": url,
                            "username": username,
                            "platform": "Instagram",
                        }
                    return {"found": False}
        except Exception as e:
            return {"found": False, "error": str(e)}

    async def _check_twitter(self, username: str) -> dict:
        """Check Twitter/X profile using API if available."""
        # Use bearer token if available
        if self.config.has_api_key("twitter_bearer_token"):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    headers = {
                        "Authorization": f"Bearer {self.config.twitter_bearer_token}",
                    }
                    url = f"https://api.twitter.com/2/users/by/username/{username}?user.fields=description,created_at,public_metrics,verified,location,profile_image_url"
                    async with session.get(url, headers=headers) as resp:
                        if resp.status == 200:
                            data = (await resp.json()).get("data", {})
                            metrics = data.get("public_metrics", {})
                            return {
                                "found": True,
                                "url": f"https://x.com/{username}",
                                "username": data.get("username", username),
                                "display_name": data.get("name"),
                                "bio": data.get("description"),
                                "location": data.get("location"),
                                "followers": metrics.get("followers_count"),
                                "following": metrics.get("following_count"),
                                "posts": metrics.get("tweet_count"),
                                "verified": data.get("verified", False),
                                "created_at": data.get("created_at"),
                                "profile_image": data.get("profile_image_url"),
                                "platform": "Twitter/X",
                            }
            except Exception as e:
                return {"found": False, "error": str(e)}

        # Fallback: basic check
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                url = f"https://x.com/{username}"
                headers = {"User-Agent": self.config.user_agent}
                async with session.get(url, headers=headers, allow_redirects=False) as resp:
                    return {
                        "found": resp.status == 200,
                        "url": url,
                        "username": username,
                        "platform": "Twitter/X",
                    }
        except Exception:
            return {"found": False}

    async def _check_reddit(self, username: str) -> dict:
        """Check Reddit profile via public JSON API."""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                url = f"https://www.reddit.com/user/{username}/about.json"
                headers = {"User-Agent": "Ghost-OSINT/1.0"}
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = (await resp.json()).get("data", {})
                        return {
                            "found": True,
                            "url": f"https://www.reddit.com/user/{username}",
                            "username": data.get("name", username),
                            "display_name": data.get("subreddit", {}).get("title", ""),
                            "bio": data.get("subreddit", {}).get("public_description", ""),
                            "karma_post": data.get("link_karma", 0),
                            "karma_comment": data.get("comment_karma", 0),
                            "created_at": data.get("created_utc"),
                            "verified": data.get("verified", False),
                            "is_gold": data.get("is_gold", False),
                            "platform": "Reddit",
                        }
                    return {"found": False}
        except Exception as e:
            return {"found": False, "error": str(e)}

    async def _check_tiktok(self, username: str) -> dict:
        """Check TikTok profile."""
        url = f"https://www.tiktok.com/@{username}"
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                headers = {"User-Agent": self.config.user_agent}
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        return {
                            "found": True,
                            "url": url,
                            "username": username,
                            "platform": "TikTok",
                        }
                    return {"found": False}
        except Exception as e:
            return {"found": False, "error": str(e)}

    async def _check_github(self, username: str) -> dict:
        """Check GitHub profile via public API."""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                url = f"https://api.github.com/users/{username}"
                headers = {"User-Agent": "Ghost-OSINT/1.0", "Accept": "application/vnd.github.v3+json"}
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            "found": True,
                            "url": data.get("html_url"),
                            "username": data.get("login"),
                            "display_name": data.get("name"),
                            "bio": data.get("bio"),
                            "location": data.get("location"),
                            "company": data.get("company"),
                            "blog": data.get("blog"),
                            "followers": data.get("followers"),
                            "following": data.get("following"),
                            "public_repos": data.get("public_repos"),
                            "created_at": data.get("created_at"),
                            "platform": "GitHub",
                        }
                    return {"found": False}
        except Exception as e:
            return {"found": False, "error": str(e)}

    async def _check_linkedin(self, username: str) -> dict:
        """Check LinkedIn profile (basic existence check)."""
        url = f"https://www.linkedin.com/in/{username}"
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                headers = {"User-Agent": self.config.user_agent}
                async with session.get(url, headers=headers, allow_redirects=False) as resp:
                    return {
                        "found": resp.status == 200,
                        "url": url,
                        "username": username,
                        "platform": "LinkedIn",
                    }
        except Exception:
            return {"found": False}
