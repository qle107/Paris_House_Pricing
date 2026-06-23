"""Municipal planning document discovery (feeds the AI agent)."""
from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from rei.common.db import connection
from rei.ingestion.base import Collector


class MinutesCollector(Collector):
    source_id = "municipal_minutes"
    rps = 1.0  # be polite to municipal servers
    keywords = ("deliberation", "conseil municipal", "compte-rendu", "compte rendu", "seance")

    def discover_pdfs(self, root_url: str, max_pages: int = 1) -> list[str]:
        """Find links to deliberation/minutes PDFs on a council page."""
        html = self.http.get(root_url).text
        soup = BeautifulSoup(html, "lxml")
        found: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = (a.get_text() or "").lower()
            if href.lower().endswith(".pdf") and any(k in text or k in href.lower() for k in self.keywords):
                found.append(urljoin(root_url, href))
        return sorted(set(found))

    def register(self, insee: str, url: str, doc_type: str = "deliberation") -> None:
        with connection() as conn:
            from sqlalchemy import text
            conn.execute(
                text(
                    "INSERT INTO docs.document (code_commune, doc_type, source_url, host, discovered_at, status) "
                    "VALUES (:c, :t, :u, :h, now(), 'discovered') ON CONFLICT (source_url) DO NOTHING"
                ),
                {"c": insee, "t": doc_type, "u": url, "h": urlparse(url).netloc},
            )

    def collect(self, sites: dict[str, str] | None = None) -> int:
        """`sites` maps INSEE code -> council/minutes page URL."""
        if not sites:
            raise ValueError("Provide {insee: url} sites mapping")
        n = 0
        for insee, url in sites.items():
            for pdf in self.discover_pdfs(url):
                self.register(insee, pdf)
                n += 1
        return n


class ConsultationCollector(MinutesCollector):
    source_id = "public_consultations"
    keywords = ("concertation", "enquete publique", "consultation", "registre")


class RegionalPlanCollector(MinutesCollector):
    source_id = "regional_plans"
    keywords = ("sraddet", "sdrif", "schema regional", "plan regional")
