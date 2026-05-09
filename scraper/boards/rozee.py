"""
Rozee.pk job parser using Scrapling.

Rozee is Pakistan's leading job portal.  Job details load in a side panel
on the listing page (no separate detail URL), so all data is extracted
from listing-page cards.
"""

from typing import Optional, List, Any
from core.state import JobData
from .base import BaseJobParser


class RozeeParser(BaseJobParser):
    """Rozee.pk job board parser - extracts jobs from listing cards."""

    board_name = "rozee"

    def __init__(self):
        self._listing_jobs: List[JobData] = []

    def parse_job(self, response: Any) -> Optional[JobData]:
        """Not used - Rozee data is extracted in parse_listing."""
        return None

    def parse_listing(self, response: Any) -> List[str]:
        """
        Extract full job data from Rozee listing page cards.

        Rozee loads job details in a side panel, so individual job URLs
        return 503.  We extract everything from the card elements and
        store results in self._listing_jobs.  Returns an empty list so
        the spider skips per-URL fetching.
        """
        self._listing_jobs = []

        try:
            cards = response.css("div.job")
            if not cards:
                print("Rozee: No job cards found")
                return []

            for card in cards:
                try:
                    job = self._parse_card(card)
                    if job:
                        self._listing_jobs.append(job)
                except Exception as e:
                    print(f"Rozee: Card parse error: {e}")
                    continue

            print(f"Rozee: Extracted {len(self._listing_jobs)} jobs from listing")

        except Exception as e:
            print(f"Rozee listing parse error: {e}")

        return []

    def _parse_card(self, card: Any) -> Optional[JobData]:
        """Extract job data from a single listing card element."""
        # Title + URL
        title_link = self._css_first(card, ["div.jhead h3 a", "h3.s-18 a"])
        if not title_link:
            return None

        title_bdi = title_link.css("bdi")
        title_text = self.clean_text(
            self._get_text(title_bdi[0]) if title_bdi else self._get_text(title_link)
        )
        if not title_text:
            return None

        raw_url = title_link.attrib.get("href", "")
        job_url = self._normalise_url(raw_url)

        # Company + location from div.cname
        company_text = "Unknown"
        location_text = "Pakistan"
        cname = card.css("div.cname a")
        if cname:
            company_text = self.clean_text(self._get_text(cname[0])).rstrip(",") or "Unknown"
            if len(cname) > 1:
                loc = self.clean_text(self._get_text(cname[1])).strip(", ")
                location_text = loc if loc else "Pakistan"

        # Description from jbody
        desc_elem = self._css_first(card, ["div.jbody"])
        description_text = self.clean_text(self._get_text(desc_elem)) if desc_elem else ""

        # Posted date
        posted_date = None
        date_elem = self._css_first(card, ['span[data-original-title="Posted On"]'])
        if date_elem:
            posted_date = self.clean_text(self._get_text(date_elem))

        # Experience
        experience_required = None
        exp_elem = self._css_first(card, ["span.func-area-drn"])
        if exp_elem:
            experience_required = self.clean_text(self._get_text(exp_elem))

        # Employment type
        employment_type = None
        emp_elem = self._css_first(card, ["div.jcnt.font16"])
        if emp_elem:
            emp_text = self._get_text(emp_elem).lower()
            if "full" in emp_text:
                employment_type = "full-time"
            elif "part" in emp_text:
                employment_type = "part-time"
            elif "contract" in emp_text:
                employment_type = "contract"
            elif "intern" in emp_text:
                employment_type = "internship"

        job_id = self.generate_job_id(title_text, company_text, location_text)

        job_data: JobData = {
            "job_id": job_id,
            "title": title_text,
            "company": company_text,
            "location": location_text,
            "job_url": job_url,
            "board": self.board_name,
            "description": description_text,
            "skills": [],
            "posted_date": posted_date,
            "salary": None,
            "employment_type": employment_type,
            "experience_required": experience_required,
            "raw_html": "",
        }

        if self.validate_job_data(job_data):
            return job_data
        return None

    def validate_job_data(self, data: dict) -> bool:
        for field in ["title", "company", "location", "job_url"]:
            if not data.get(field):
                print(f"Rozee: Missing required field: {field}")
                return False
        return True

    @staticmethod
    def _normalise_url(raw: str) -> str:
        if not raw or raw.startswith("javascript"):
            return ""
        if raw.startswith("//"):
            return f"https:{raw}"
        if not raw.startswith("http"):
            return f"https://www.rozee.pk{raw}"
        return raw

    def build_search_url(self, query: str, location: str = "", page: int = 1) -> str:
        import urllib.parse
        query_encoded = urllib.parse.quote(query)

        url = f"https://www.rozee.pk/job/jsearch/q/{query_encoded}"

        if location:
            location_encoded = urllib.parse.quote(location)
            url += f"/lc/{location_encoded}"

        if page > 1:
            url += f"/page/{page}"

        return url


def parse_rozee_job(response: Any) -> Optional[JobData]:
    """Convenience function for Rozee job parsing."""
    parser = RozeeParser()
    return parser.parse_job(response)
