# scrapers/base_scraper.py

from abc import ABC, abstractmethod

class BaseScraper(ABC):

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        pass

    @abstractmethod
    def scrape(self, url: str) -> dict:
        pass
