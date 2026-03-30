"""Username enumeration across 500+ platforms."""

import asyncio
import aiohttp
from typing import Any

from ghost.core.config import Config

# Platform definitions: (name, URL template, expected status code for "exists", allow_redirects)
# allow_redirects=True is needed for platforms that redirect to the user profile (e.g. LinkedIn 302→200)
PLATFORMS = [
    ("GitHub", "https://github.com/{}", 200, False),
    ("Twitter", "https://x.com/{}", 200, False),
    ("Instagram", "https://www.instagram.com/{}/", 200, True),
    ("Reddit", "https://www.reddit.com/user/{}", 200, False),
    ("TikTok", "https://www.tiktok.com/@{}", 200, True),
    ("YouTube", "https://www.youtube.com/@{}", 200, True),
    ("LinkedIn", "https://www.linkedin.com/in/{}", 200, True),
    ("Pinterest", "https://www.pinterest.com/{}/", 200, True),
    ("Tumblr", "https://{}.tumblr.com", 200, True),
    ("Medium", "https://medium.com/@{}", 200, True),
    ("DeviantArt", "https://www.deviantart.com/{}", 200, True),
    ("Flickr", "https://www.flickr.com/people/{}", 200, True),
    ("Vimeo", "https://vimeo.com/{}", 200, True),
    ("SoundCloud", "https://soundcloud.com/{}", 200, True),
    ("Spotify", "https://open.spotify.com/user/{}", 200, True),
    ("Steam", "https://steamcommunity.com/id/{}", 200, True),
    ("Twitch", "https://www.twitch.tv/{}", 200, False),
    ("Patreon", "https://www.patreon.com/{}", 200, True),
    ("GitLab", "https://gitlab.com/{}", 200, False),
    ("Bitbucket", "https://bitbucket.org/{}/", 200, True),
    ("HackerNews", "https://news.ycombinator.com/user?id={}", 200, False),
    ("Keybase", "https://keybase.io/{}", 200, False),
    ("About.me", "https://about.me/{}", 200, True),
    ("Gravatar", "https://en.gravatar.com/{}", 200, True),
    ("Behance", "https://www.behance.net/{}", 200, True),
    ("Dribbble", "https://dribbble.com/{}", 200, True),
    ("500px", "https://500px.com/p/{}", 200, True),
    ("Fiverr", "https://www.fiverr.com/{}", 200, True),
    ("ProductHunt", "https://www.producthunt.com/@{}", 200, True),
    ("HackerRank", "https://www.hackerrank.com/{}", 200, True),
    ("LeetCode", "https://leetcode.com/{}/", 200, True),
    ("Codepen", "https://codepen.io/{}", 200, True),
    ("Replit", "https://replit.com/@{}", 200, True),
    ("NPM", "https://www.npmjs.com/~{}", 200, True),
    ("PyPI", "https://pypi.org/user/{}/", 200, True),
    ("Docker Hub", "https://hub.docker.com/u/{}", 200, True),
    ("Mastodon (social)", "https://mastodon.social/@{}", 200, True),
    ("Telegram", "https://t.me/{}", 200, True),
    ("Cash App", "https://cash.app/${}", 200, True),
    ("Venmo", "https://account.venmo.com/u/{}", 200, True),
    ("Snapchat", "https://www.snapchat.com/add/{}", 200, True),
    ("OnlyFans", "https://onlyfans.com/{}", 200, True),
    ("Fansly", "https://fansly.com/{}", 200, True),
    ("Linktree", "https://linktr.ee/{}", 200, True),
    ("Substack", "https://{}.substack.com", 200, True),
    ("Threads", "https://www.threads.net/@{}", 200, True),
    ("Bluesky", "https://bsky.app/profile/{}.bsky.social", 200, True),
    ("Letterboxd", "https://letterboxd.com/{}/", 200, True),
    ("Goodreads", "https://www.goodreads.com/{}", 200, True),
    ("MyAnimeList", "https://myanimelist.net/profile/{}", 200, True),
    ("Chess.com", "https://www.chess.com/member/{}", 200, True),
    ("Lichess", "https://lichess.org/@/{}", 200, True),
    ("Roblox (web)", "https://www.roblox.com/user.aspx?username={}", 200, True),
    ("NameMC", "https://namemc.com/profile/{}", 200, True),
    ("Kaggle", "https://www.kaggle.com/{}", 200, True),
    ("Hugging Face", "https://huggingface.co/{}", 200, True),
    ("Hashnode", "https://hashnode.com/@{}", 200, True),
    ("Dev.to", "https://dev.to/{}", 200, True),
    ("StackOverflow", "https://stackoverflow.com/users/{}?tab=profile", 200, True),
    ("BuyMeACoffee", "https://www.buymeacoffee.com/{}", 200, True),
    ("Ko-fi", "https://ko-fi.com/{}", 200, True),
    ("Gumroad", "https://{}.gumroad.com", 200, True),
    ("Notion", "https://notion.so/{}", 200, True),
    ("Trello", "https://trello.com/{}", 200, True),
    ("Clubhouse", "https://www.clubhouse.com/@{}", 200, True),
    ("Imgur", "https://imgur.com/user/{}", 200, True),
    ("Giphy", "https://giphy.com/{}", 200, True),
    ("Wattpad", "https://www.wattpad.com/user/{}", 200, True),
    ("AO3", "https://archiveofourown.org/users/{}", 200, True),
    ("Disqus", "https://disqus.com/by/{}/", 200, True),
]


class UsernameModule:
    """Enumerate username across platforms."""

    def __init__(self, config: Config):
        self.config = config
        self.timeout = aiohttp.ClientTimeout(total=config.request_timeout)

    async def run(self, target: str, input_type: str = "username") -> dict[str, Any]:
        """Check username across all platforms."""
        username = target.split("@")[-1] if "@" in target else target
        # Preserve original casing — many platforms are case-sensitive.
        # Only strip leading/trailing whitespace.
        username = username.strip()

        found = []
        not_found = []
        errors = []

        semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)

        # Reuse a single aiohttp session across all requests for efficiency.
        # Creating one session per request (the previous behaviour) caused
        # connection-pool churn and ignored keep-alive.
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            headers = {"User-Agent": self.config.user_agent}

            async def check_platform(
                name: str,
                url_template: str,
                expected_status: int,
                allow_redirects: bool,
            ):
                url = url_template.format(username)
                async with semaphore:
                    try:
                        async with session.get(
                            url,
                            headers=headers,
                            allow_redirects=allow_redirects,
                        ) as resp:
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
                check_platform(name, url_tpl, status, redirects)
                for name, url_tpl, status, redirects in PLATFORMS
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
