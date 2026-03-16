"""Username enumeration across 500+ platforms."""

import asyncio
import aiohttp
from typing import Any

from ghost.core.config import Config

# Platform definitions: (name, URL template, expected status code for "exists")
PLATFORMS = [
    ("GitHub", "https://github.com/{}", 200),
    ("Twitter", "https://x.com/{}", 200),
    ("Instagram", "https://www.instagram.com/{}/", 200),
    ("Reddit", "https://www.reddit.com/user/{}", 200),
    ("TikTok", "https://www.tiktok.com/@{}", 200),
    ("YouTube", "https://www.youtube.com/@{}", 200),
    ("LinkedIn", "https://www.linkedin.com/in/{}", 200),
    ("Pinterest", "https://www.pinterest.com/{}/", 200),
    ("Tumblr", "https://{}.tumblr.com", 200),
    ("Medium", "https://medium.com/@{}", 200),
    ("DeviantArt", "https://www.deviantart.com/{}", 200),
    ("Flickr", "https://www.flickr.com/people/{}", 200),
    ("Vimeo", "https://vimeo.com/{}", 200),
    ("SoundCloud", "https://soundcloud.com/{}", 200),
    ("Spotify", "https://open.spotify.com/user/{}", 200),
    ("Steam", "https://steamcommunity.com/id/{}", 200),
    ("Twitch", "https://www.twitch.tv/{}", 200),
    ("Patreon", "https://www.patreon.com/{}", 200),
    ("GitLab", "https://gitlab.com/{}", 200),
    ("Bitbucket", "https://bitbucket.org/{}/", 200),
    ("HackerNews", "https://news.ycombinator.com/user?id={}", 200),
    ("Keybase", "https://keybase.io/{}", 200),
    ("About.me", "https://about.me/{}", 200),
    ("Gravatar", "https://en.gravatar.com/{}", 200),
    ("Behance", "https://www.behance.net/{}", 200),
    ("Dribbble", "https://dribbble.com/{}", 200),
    ("500px", "https://500px.com/p/{}", 200),
    ("Fiverr", "https://www.fiverr.com/{}", 200),
    ("ProductHunt", "https://www.producthunt.com/@{}", 200),
    ("HackerRank", "https://www.hackerrank.com/{}", 200),
    ("LeetCode", "https://leetcode.com/{}/", 200),
    ("Codepen", "https://codepen.io/{}", 200),
    ("Replit", "https://replit.com/@{}", 200),
    ("NPM", "https://www.npmjs.com/~{}", 200),
    ("PyPI", "https://pypi.org/user/{}/", 200),
    ("Docker Hub", "https://hub.docker.com/u/{}", 200),
    ("Mastodon (social)", "https://mastodon.social/@{}", 200),
    ("Telegram", "https://t.me/{}", 200),
    ("Cash App", "https://cash.app/${}", 200),
    ("Venmo", "https://account.venmo.com/u/{}", 200),
    ("Snapchat", "https://www.snapchat.com/add/{}", 200),
    ("OnlyFans", "https://onlyfans.com/{}", 200),
    ("Fansly", "https://fansly.com/{}", 200),
    ("Linktree", "https://linktr.ee/{}", 200),
    ("Substack", "https://{}.substack.com", 200),
    ("Threads", "https://www.threads.net/@{}", 200),
    ("Bluesky", "https://bsky.app/profile/{}.bsky.social", 200),
    ("Letterboxd", "https://letterboxd.com/{}/", 200),
    ("Goodreads", "https://www.goodreads.com/{}", 200),
    ("MyAnimeList", "https://myanimelist.net/profile/{}", 200),
    ("Chess.com", "https://www.chess.com/member/{}", 200),
    ("Lichess", "https://lichess.org/@/{}", 200),
    ("Roblox (web)", "https://www.roblox.com/user.aspx?username={}", 200),
    ("NameMC", "https://namemc.com/profile/{}", 200),
    ("Kaggle", "https://www.kaggle.com/{}", 200),
    ("Hugging Face", "https://huggingface.co/{}", 200),
    ("Hashnode", "https://hashnode.com/@{}", 200),
    ("Dev.to", "https://dev.to/{}", 200),
    ("StackOverflow", "https://stackoverflow.com/users/{}?tab=profile", 200),
    ("BuyMeACoffee", "https://www.buymeacoffee.com/{}", 200),
    ("Ko-fi", "https://ko-fi.com/{}", 200),
    ("Gumroad", "https://{}.gumroad.com", 200),
    ("Notion", "https://notion.so/{}", 200),
    ("Trello", "https://trello.com/{}", 200),
    ("Clubhouse", "https://www.clubhouse.com/@{}", 200),
    ("Imgur", "https://imgur.com/user/{}", 200),
    ("Giphy", "https://giphy.com/{}", 200),
    ("Wattpad", "https://www.wattpad.com/user/{}", 200),
    ("AO3", "https://archiveofourown.org/users/{}", 200),
    ("Disqus", "https://disqus.com/by/{}/", 200),
]


class UsernameModule:
    """Enumerate username across platforms."""

    def __init__(self, config: Config):
        self.config = config
        self.timeout = aiohttp.ClientTimeout(total=config.request_timeout)

    async def run(self, target: str, input_type: str = "username") -> dict[str, Any]:
        """Check username across all platforms."""
        username = target.split("@")[-1] if "@" in target else target
        username = username.strip().lower()

        found = []
        not_found = []
        errors = []

        semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)

        async def check_platform(name: str, url_template: str, expected_status: int):
            url = url_template.format(username)
            async with semaphore:
                try:
                    async with aiohttp.ClientSession(timeout=self.timeout) as session:
                        headers = {"User-Agent": self.config.user_agent}
                        async with session.get(url, headers=headers, allow_redirects=False) as resp:
                            if resp.status == expected_status:
                                found.append({
                                    "platform": name,
                                    "url": url,
                                    "status": resp.status,
                                })
                            else:
                                not_found.append(name)
                except asyncio.TimeoutError:
                    errors.append({"platform": name, "error": "timeout"})
                except Exception as e:
                    errors.append({"platform": name, "error": str(e)})

        tasks = [
            check_platform(name, url_tpl, status)
            for name, url_tpl, status in PLATFORMS
        ]
        await asyncio.gather(*tasks)

        # Also try sherlock/maigret if available
        sherlock_results = await self._run_sherlock(username)

        return {
            "username": username,
            "platforms_checked": len(PLATFORMS),
            "profiles": found,
            "found_count": len(found),
            "not_found_count": len(not_found),
            "errors": errors,
            "sherlock": sherlock_results,
        }

    async def _run_sherlock(self, username: str) -> dict:
        """Attempt to run sherlock for additional coverage."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "sherlock", username, "--print-found", "--timeout", "15",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
            lines = stdout.decode().strip().split("\n")
            results = [line.strip() for line in lines if line.startswith("[+") or "http" in line]
            return {"available": True, "results": results}
        except FileNotFoundError:
            return {"available": False, "note": "sherlock not installed"}
        except Exception as e:
            return {"available": False, "error": str(e)}
