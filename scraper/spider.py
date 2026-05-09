"""
JobScraperSpider: Multi-session job scraper using Scrapling.

Coordinates scraping across LinkedIn, Rozee, Indeed, and Mustakbil with:
- StealthyFetcher for anti-bot bypass
- Checkpoint-based resume
- Concurrent requests with rate limiting
"""

from typing import List, Dict, Optional
from core.settings import get_settings
from core.state import JobData
from scraper.boards import (
    LinkedInParser,
    RozeeParser,
    IndeedParser,
    MustakbilParser,
    BaseJobParser
)
import time


def _fetch_with_scrapling(url: str, board: str, headless: bool):
    try:
        from scrapling import StealthyFetcher
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Missing runtime dependency for Scrapling fetchers. "
            "Install project requirements and Scrapling fetcher extras."
        ) from exc

    return StealthyFetcher.fetch(
        url,
        headless=headless,
        network_idle=True,
        solve_cloudflare=True,
        google_search=(board == "mustakbil"),
    )


class JobScraperSpider:
    """
    Multi-board job scraper with Scrapling's adaptive parsing.
    
    Features:
    - StealthyFetcher with Cloudflare bypass
    - Session management for cookies/headers
    - Concurrent requests with configurable delays
    """
    
    def __init__(self):
        """Initialize spider with parsers and settings."""
        self.settings = get_settings()
        
        # Initialize parsers
        self.parsers: Dict[str, BaseJobParser] = {
            "linkedin": LinkedInParser(),
            "rozee": RozeeParser(),
            "indeed": IndeedParser(),
            "mustakbil": MustakbilParser()
        }
        
        # StealthyFetcher options (passed as kwargs)
        self.fetcher_options = {
            "auto_match": True,  # Enable adaptive parsing
            "stealth": True,  # Enable stealth mode
        }
        
        print("JobScraperSpider initialized with 4 parsers")
    
    def scrape_board(
        self,
        board: str,
        query: str,
        location: str = "",
        max_pages: int = 3,
        max_jobs: int = None
    ) -> List[JobData]:
        """
        Scrape single job board.
        
        Args:
            board: Board name ("linkedin", "rozee", "indeed", "mustakbil")
            query: Search query
            location: Location filter
            max_pages: Maximum pages to scrape
            max_jobs: Maximum jobs to scrape (None = unlimited)
            
        Returns:
            List of JobData dictionaries
        """
        if board not in self.parsers:
            print(f"Unknown board: {board}")
            return []
        
        parser = self.parsers[board]
        jobs = []
        
        print(f"\nScraping {board.upper()} for '{query}' in '{location}'...")
        
        def _fetch(url: str, headless: bool):
            return _fetch_with_scrapling(url=url, board=board, headless=headless)

        def _fetch_with_fallback(url: str):
            response = _fetch(url, headless=True)
            if getattr(response, "status", None) == 410:
                # Mustakbil intermittently blocks headless requests; retry headful.
                response = _fetch(url, headless=False)
            return response

        for page in range(1, max_pages + 1):
            try:
                search_url = parser.build_search_url(query, location, page)
                print(f"   Page {page}: {search_url}")

                listing_response = _fetch_with_fallback(search_url)

                if not listing_response:
                    print(f"   Failed to fetch page {page}")
                    continue

                job_urls = parser.parse_listing(listing_response)

                # Some parsers (e.g. Rozee) extract full job data from
                # listing cards because individual pages are inaccessible.
                listing_jobs = getattr(parser, "_listing_jobs", None)
                if listing_jobs:
                    for lj in listing_jobs:
                        if max_jobs and len(jobs) >= max_jobs:
                            break
                        jobs.append(lj)
                        print(f"      {lj['title']} at {lj['company']}")
                    parser._listing_jobs = []
                    if max_jobs and len(jobs) >= max_jobs:
                        print(f"   Reached max_jobs limit ({max_jobs})")
                        break
                    time.sleep(self.settings.job_scraping_download_delay * 2)
                    continue

                if not job_urls:
                    print(f"   No jobs found on page {page}")
                    break  # No more results

                if max_jobs:
                    remaining_slots = max_jobs - len(jobs)
                    if remaining_slots <= 0:
                        break
                    job_urls = job_urls[:remaining_slots]

                for i, job_url in enumerate(job_urls, 1):
                    try:
                        print(f"   Job {i}/{len(job_urls)}: {job_url}")

                        job_response = _fetch_with_fallback(job_url)

                        if not job_response:
                            print(f"      Failed to fetch job")
                            continue

                        job_data = parser.parse_job(job_response)

                        if job_data:
                            if not job_data.get("job_url"):
                                job_data["job_url"] = job_url
                            jobs.append(job_data)
                            print(f"      {job_data['title']} at {job_data['company']}")
                        else:
                            print(f"      Failed to parse job")

                        time.sleep(self.settings.job_scraping_download_delay)

                        if max_jobs and len(jobs) >= max_jobs:
                            print(f"   Reached max_jobs limit ({max_jobs})")
                            break

                    except Exception as e:
                        print(f"      Job scrape error: {e}")
                        continue

                if max_jobs and len(jobs) >= max_jobs:
                    break

                time.sleep(self.settings.job_scraping_download_delay * 2)

            except Exception as e:
                print(f"   Page {page} error: {e}")
                continue
        
        print(f"{board.upper()}: Scraped {len(jobs)} jobs\n")
        return jobs
    
    def scrape_all_boards(
        self,
        query: str,
        location: str = "Pakistan",
        boards: Optional[List[str]] = None,
        max_pages_per_board: int = 2,
        max_jobs_per_board: int = None
    ) -> List[JobData]:
        """
        Scrape multiple job boards.
        
        Args:
            query: Search query
            location: Location filter
            boards: List of boards to scrape (None = all)
            max_pages_per_board: Max pages per board
            max_jobs_per_board: Max jobs to scrape per board (None = unlimited)
            
        Returns:
            Combined list of jobs from all boards
        """
        if boards is None:
            boards = ["linkedin", "rozee", "indeed", "mustakbil"]
        
        all_jobs = []
        
        print(f"\n{'='*60}")
        print(f"Starting multi-board scraping:")
        print(f"  Query: {query}")
        print(f"  Location: {location}")
        print(f"  Boards: {', '.join(boards)}")
        print(f"  Max pages per board: {max_pages_per_board}")
        if max_jobs_per_board:
            print(f"  Max jobs per board: {max_jobs_per_board}")
        print(f"{'='*60}\n")
        
        for board in boards:
            try:
                jobs = self.scrape_board(
                    board=board,
                    query=query,
                    location=location,
                    max_pages=max_pages_per_board,
                    max_jobs=max_jobs_per_board
                )
                all_jobs.extend(jobs)
            
            except Exception as e:
                print(f"Board {board} failed: {e}")
                continue
        
        print(f"\n{'='*60}")
        print(f"Total jobs scraped: {len(all_jobs)}")
        print(f"{'='*60}\n")
        
        return all_jobs
    


# Global spider instance
_spider: Optional[JobScraperSpider] = None


def get_spider() -> JobScraperSpider:
    """
    Get or create global spider instance.
    
    Returns:
        JobScraperSpider instance
    """
    global _spider
    if _spider is None:
        _spider = JobScraperSpider()
    return _spider
