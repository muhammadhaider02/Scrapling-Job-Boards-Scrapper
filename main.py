"""
Bulk pipeline runner for all permitted roles:
Scraping -> Enrichment/Cleaning/Skill extraction -> Optional vetting -> DB upsert.

Run this to execute the end-to-end scout stack in one go.
"""

import sys
import os
from contextlib import contextmanager

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.state import AgentState
from pipeline.enricher_node import job_enricher_node
from langchain_core.messages import HumanMessage
from core.settings import get_settings
from services.supabase import get_supabase_service
from services.redis import get_redis_service
from scraper.spider import get_spider


def _batched(items, batch_size):
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]


@contextmanager
def _suppress_scrapling_logs():
    """Filter noisy Scrapling [INFO]/[ERROR] lines from stdout/stderr."""
    class _StreamFilter:
        def __init__(self, stream):
            self.stream = stream

        def write(self, data):
            if "] INFO:" in data or "] ERROR:" in data:
                return
            try:
                self.stream.write(data)
            except UnicodeEncodeError:
                self.stream.write(data.encode("ascii", errors="ignore").decode("ascii"))

        def flush(self):
            self.stream.flush()

    original_out = sys.stdout
    original_err = sys.stderr
    sys.stdout = _StreamFilter(original_out)
    sys.stderr = _StreamFilter(original_err)
    try:
        yield
    finally:
        sys.stdout = original_out
        sys.stderr = original_err


def run_bulk_pipeline():
    """Run scrape + enrichment for all permitted roles and upsert in batches."""
    settings = get_settings()
    roles = settings.permitted_roles
    batch_size = 200
    supabase = get_supabase_service()
    redis = get_redis_service()
    spider = get_spider()

    supabase.delete_stale_jobs(days=settings.job_stale_after_days)

    print("\n" + "=" * 78)
    print(f"RUNNING BULK PIPELINE FOR {len(roles)} ROLES")
    print("=" * 78 + "\n")

    totals = {
        "roles": len(roles),
        "scraped": 0,
        "enriched": 0,
        "vetted": 0,
        "db_upserts": 0,
        "failed_roles": 0,
    }

    for index, role in enumerate(roles, 1):
        print(f"\n[{index}/{len(roles)}] Role: {role}")
        print("-" * 60)

        state: AgentState = {
            "messages": [HumanMessage(content=f"Find {role} jobs")],
            "user_id": "bulk_scraper_admin",
            "search_query": role,
            "raw_job_list": [],
            "scraping_status": "pending",
            "current_page": 1,
            "error": None,
            "retry_count": 0,
        }

        try:
            raw_jobs = spider.scrape_all_boards(
                query=role,
                location="Pakistan",
                boards=settings.job_scraping_boards,
                max_pages_per_board=settings.job_scraping_max_pages_per_board,
                max_jobs_per_board=settings.job_scraping_max_jobs_per_board,
            )
            totals["scraped"] += len(raw_jobs)
            print(f"   Raw jobs: {len(raw_jobs)}")

            # Deduplicate via Redis
            new_jobs = []
            duplicate_count = 0
            for job in raw_jobs:
                if not redis.is_job_processed(job["job_id"]):
                    new_jobs.append(job)
                    redis.mark_job_processed(job["job_id"])
                else:
                    duplicate_count += 1

            print(f"   New jobs: {len(new_jobs)}")
            print(f"   Duplicates filtered: {duplicate_count}")

            enrich_input = dict(state)
            enrich_input["raw_job_list"] = new_jobs
            enrich_input["scraping_status"] = "completed"
            enrich_result = job_enricher_node(enrich_input)
            enriched_jobs = enrich_result.get("raw_job_list", new_jobs)
            totals["enriched"] += len(enriched_jobs)
            print(f"   Enriched jobs: {len(enriched_jobs)}")

            # Vetting disabled: keep all enriched jobs.
            # Persist enriched jobs to DB in explicit batches.
            if enriched_jobs:
                affected_for_role = 0
                for batch in _batched(enriched_jobs, batch_size):
                    affected_for_role += int(supabase.bulk_insert_jobs(batch) or 0)
                totals["db_upserts"] += affected_for_role
                print(f"   DB upserts (batched): {affected_for_role}")

        except Exception as exc:
            totals["failed_roles"] += 1
            print(f"   Role failed: {exc}")

    print("\n" + "=" * 78)
    print("BULK PIPELINE SUMMARY")
    print(f"Roles processed: {totals['roles']}")
    print(f"Roles failed: {totals['failed_roles']}")
    print(f"Jobs scraped: {totals['scraped']}")
    print(f"Jobs enriched: {totals['enriched']}")
    print(f"Jobs vetted: {totals['vetted']}")
    print(f"DB upserts: {totals['db_upserts']}")
    print("=" * 78 + "\n")

    return totals


if __name__ == "__main__":
    with _suppress_scrapling_logs():
        run_bulk_pipeline()
