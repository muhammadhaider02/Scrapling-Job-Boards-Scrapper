"""
Environment-backed settings for the standalone scraper.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

from dotenv import load_dotenv


@dataclass
class Settings:
    supabase_url: str
    supabase_service_role_key: str
    redis_url: str
    redis_max_retries: int
    redis_job_queue_prefix: str
    redis_processed_ttl: int
    job_scraping_max_pages_per_board: int
    job_scraping_max_jobs_per_board: int
    job_scraping_download_delay: float
    permitted_roles: List[str]
    excel_skill_gap: str
    job_stale_after_days: int


_settings: Settings | None = None


def _get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _parse_permitted_roles(raw: str | None) -> List[str]:
    if not raw:
        return ["Software Engineer", "Backend Developer", "Data Engineer"]

    raw = raw.strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except json.JSONDecodeError:
        pass

    return [part.strip() for part in raw.split(",") if part.strip()]


def _build_settings() -> Settings:
    load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=False)

    return Settings(
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        redis_max_retries=_get_env_int("REDIS_MAX_RETRIES", 3),
        redis_job_queue_prefix=os.getenv("REDIS_JOB_QUEUE_PREFIX", "jobs"),
        redis_processed_ttl=_get_env_int("REDIS_PROCESSED_TTL", 86400),
        job_scraping_max_pages_per_board=_get_env_int("JOB_SCRAPING_MAX_PAGES_PER_BOARD", 2),
        job_scraping_max_jobs_per_board=_get_env_int("JOB_SCRAPING_MAX_JOBS_PER_BOARD", 50),
        job_scraping_download_delay=_get_env_float(
            "JOB_SCRAPING_DOWNLOAD_DELAY",
            _get_env_float("DOWNLOAD_DELAY", 2.0),
        ),
        permitted_roles=_parse_permitted_roles(os.getenv("PERMITTED_ROLES")),
        excel_skill_gap=os.getenv("EXCEL_SKILL_GAP", "data/skills_master.xlsx"),
        job_stale_after_days=_get_env_int("JOB_STALE_AFTER_DAYS", 7),
    )


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = _build_settings()
    return _settings

