# scrapers/mangadex.py

from ._base_scraper import BaseScraper

class MangaDexScraper(BaseScraper):

    def can_handle(self, url: str) -> bool:
        return "mangadex.org/title" in url

    def scrape(self, url: str) -> dict:
        # Placeholder — easy to add later
        return {
            "title": "Unknown MangaDex Title",
            "chapter_count": 0,
            "genres": [],
            "source": url
        }
