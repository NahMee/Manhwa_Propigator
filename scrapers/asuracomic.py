import requests
from bs4 import BeautifulSoup
from ._base_scraper import BaseScraper

class AsuraComicScraper(BaseScraper):

    def can_handle(self, url: str) -> bool:
        return "asuracomic.net/series" in url

    def scrape(self, url: str) -> dict:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, "html.parser")

        # --- TITLE ---
        title_tag = soup.find("span", class_="text-xl font-bold")
        title = title_tag.get_text(strip=True) if title_tag else "Unknown"

        # --- CHAPTER COUNT ---
        chapter_count = 0
        chapter_tags = soup.find_all("span", class_="pl-[1px]")
        if chapter_tags:
            raw = chapter_tags[-1].get_text(strip=True)
            try:
                chapter_count = int(raw)
            except ValueError:
                chapter_count = 0

        # --- GENRES ---
        genres = []
        genres_section = soup.find("h3", string=lambda x: x and "Genres" in x)
        if genres_section:
            genres_container = genres_section.find_next("div")
            if genres_container:
                for btn in genres_container.find_all("button"):
                    genres.append(btn.get_text(strip=True))

        # --- THUMBNAIL URL ---
        thumbnail_url = None
        img_tag = soup.find("img", alt="poster", loading="lazy")
        if img_tag and img_tag.get("src"):
            thumbnail_url = img_tag["src"]

        return {
            "title": title,
            "chapter_count": chapter_count,
            "genres": genres,
            "source": url,
            "thumbnail_url": thumbnail_url
        }
