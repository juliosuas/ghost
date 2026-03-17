"""Ghost OSINT collection modules.

This module provides a collection of tools for Open-Source Intelligence (OSINT) collection.
"""

import os
import requests
from bs4 import BeautifulSoup
from typing import List, Dict


def fetch_url(url: str) -> str:
    """Fetch the content of a URL.

    Args:
    url (str): The URL to fetch.

    Returns:
    str: The content of the URL.

    Raises:
    requests.RequestException: If the request fails.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching URL: {e}")
        return None


def parse_html(html: str) -> BeautifulSoup:
    """Parse HTML content using BeautifulSoup.

    Args:
    html (str): The HTML content to parse.

    Returns:
    BeautifulSoup: The parsed HTML content.
    """
    return BeautifulSoup(html, "html.parser")


def extract_links(html: BeautifulSoup) -> List[str]:
    """Extract links from HTML content.

    Args:
    html (BeautifulSoup): The HTML content to extract links from.

    Returns:
    List[str]: A list of extracted links.
    """
    return [a.get("href") for a in html.find_all("a") if a.get("href")]


def extract_emails(html: BeautifulSoup) -> List[str]:
    """Extract email addresses from HTML content.

    Args:
    html (BeautifulSoup): The HTML content to extract email addresses from.

    Returns:
    List[str]: A list of extracted email addresses.
    """
    return [text for text in html.find_all(text=True) if "@" in text]


class OSINTCollector:
    """A class for collecting OSINT data.

    Attributes:
    url (str): The URL to collect data from.
    """

    def __init__(self, url: str):
        """Initialize the OSINT collector.

        Args:
        url (str): The URL to collect data from.
        """
        self.url = url

    def collect_data(self) -> Dict[str, List[str]]:
        """Collect OSINT data from the specified URL.

        Returns:
        Dict[str, List[str]]: A dictionary containing the collected data.
        """
        html = fetch_url(self.url)
        if html is None:
            return {}

        soup = parse_html(html)
        links = extract_links(soup)
        emails = extract_emails(soup)

        return {"links": links, "emails": emails}


def main():
    """The main entry point of the script."""
    url = "https://example.com"
    collector = OSINTCollector(url)
    data = collector.collect_data()
    print(data)


if __name__ == "__main__":
    main()
