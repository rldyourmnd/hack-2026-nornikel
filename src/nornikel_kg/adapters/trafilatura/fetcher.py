from __future__ import annotations

from nornikel_kg.ports.parser import FetchedPage, ParserError


class TrafilaturaUrlFetcher:
    """URL -> clean main text via trafilatura, with title/date metadata."""

    def fetch(self, url: str) -> FetchedPage:
        import trafilatura

        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            raise ParserError(f"Could not download URL: {url}")
        return self.extract(url=url, html=downloaded)

    def extract(self, *, url: str, html: str) -> FetchedPage:
        import trafilatura

        text = trafilatura.extract(html, output_format="txt", with_metadata=False)
        if not text or not text.strip():
            raise ParserError(f"URL has no extractable main text: {url}")
        metadata = trafilatura.extract_metadata(html)
        title = getattr(metadata, "title", None) if metadata else None
        date = getattr(metadata, "date", None) if metadata else None
        return FetchedPage(url=url, text=text.strip(), title=title, date=date)
