<div align="center">

# Job Board Scraper

**Multi-board job scraper for Pakistan with enrichment, deduplication, and Supabase persistence**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://python.org)
[![Scrapling](https://img.shields.io/badge/Scrapling-0.4.7-FF6B35)](https://github.com/D4Vinci/Scrapling)
[![Supabase](https://img.shields.io/badge/Supabase-2.30-3ECF8E?logo=supabase&logoColor=white)](https://supabase.com)
[![Redis](https://img.shields.io/badge/Redis-7.4-DC382D?logo=redis&logoColor=white)](https://redis.io)
[![uv](https://img.shields.io/badge/uv-package%20manager-7C3AED)](https://github.com/astral-sh/uv)

Scrape LinkedIn, Indeed, Rozee.pk and Mustakbil for job listings in Pakistan. Cleans and enriches each posting, deduplicates via Redis, and upserts everything to Supabase.

</div>

---

## Table of Contents

- [Overview](#overview)
- [Pipeline](#pipeline)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)

---

## Overview

`main.py` iterates over a configured list of permitted roles and runs the full pipeline for each one. The spider fetches listing pages and individual job postings using Scrapling's `StealthyFetcher`, which handles Cloudflare challenges and anti-bot detection. Each parser extracts structured fields from the board's HTML.

New jobs are checked against a Redis processed set so duplicates are never written twice. Unique jobs pass through the enricher, which cleans the description, matches skills against a master Excel list, parses experience level and year ranges, normalises salary strings, and detects education and job type. Enriched records are upserted to Supabase in batches of 200.

A separate `digital_scout_node` in `pipeline/scout.py` handles interactive, query-driven scraping with role-allowlist enforcement. It is not called by `main.py` but is available for integration into a wider agent workflow.

---

## Pipeline

```
┌─────────────────────────────────────────────────────────┐
│  Permitted roles (PERMITTED_ROLES env var)              │
│  e.g. ["Backend Developer", "Data Engineer"]            │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Spider  (scraper/spider.py)                            │
│  StealthyFetcher with Cloudflare bypass                 │
│  One parser per board — LinkedIn, Indeed, Rozee,        │
│  Mustakbil — each with adaptive CSS selectors           │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Redis Deduplication  (services/redis.py)               │
│  SHA-256 job ID checked against processed set           │
│  TTL-based expiry (default 24 h)                        │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Enricher  (pipeline/enricher.py)                       │
│  Description cleaning + section splitting               │
│  Skill extraction from master Excel list                │
│  Experience level + year-range parsing                  │
│  Salary normalisation + education/job-type detection    │
│  Enrichment confidence score per job                    │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Supabase Upsert  (services/supabase.py)                │
│  Batched upsert on conflict (job_id)                    │
│  200 records per batch                                  │
└─────────────────────────────────────────────────────────┘
```

---

## Features

| Feature | Description |
|:---|:---|
| **Multi-board scraping** | LinkedIn, Indeed, Rozee.pk and Mustakbil in one run |
| **Anti-bot bypass** | Scrapling `StealthyFetcher` with Cloudflare solver and headless/headful fallback |
| **Role allowlist** | Only scrapes roles listed in `PERMITTED_ROLES` — rejects everything else |
| **Redis deduplication** | SHA-256 job IDs tracked in a TTL-based Redis set; duplicates never re-processed |
| **Description cleaning** | HTML entity decoding, whitespace normalisation, section splitting, sentence deduplication |
| **Skill extraction** | Word-boundary regex matching against a configurable master Excel skill list |
| **Experience parsing** | Detects level (entry/junior/mid/senior/lead) and min/max year ranges |
| **Salary normalisation** | Parses currency, amount range and period from free-text salary strings |
| **Batched upsert** | Supabase upsert in configurable batches with conflict resolution on `job_id` |
| **Enrichment confidence** | Scores each job 0–1 based on how much structured data was extracted |
| **Stale job cleanup** | Deletes jobs older than a configurable number of days at the start of each run |

---

## Tech Stack

| Layer | Technology |
|:---|:---|
| Scraping | Scrapling 0.4.7 (`StealthyFetcher`) |
| Parsers | Per-board CSS selector parsers with adaptive fallback chains |
| Enrichment | pandas, regex, openpyxl |
| Deduplication / Queue | Redis 7.4 |
| Database | Supabase (PostgreSQL via `supabase-py` 2.30) |
| State | LangChain Core (message types) |
| Runtime | Python 3.12, uv |

---

## Prerequisites

- Python 3.12+
- Redis (local or remote)
- Supabase project with service role key
- Scrapling fetcher extras (installs Playwright/Camoufox automatically via `scrapling[fetchers]`)
- Master skill list Excel file (default: `data/skills_master.xlsx`)

---

## Getting Started

```bash
git clone <repo-url>
cd Scrapling-Job-Board-Scrapper

# Install dependencies
uv sync

# Download Playwright browser binaries (required for StealthyFetcher)
uv run playwright install

# Copy and fill in environment variables
cp .env.example .env
```

Edit `.env` with your Supabase credentials and Redis URL (see [Environment Variables](#environment-variables)), then run:

```bash
uv run python main.py
```

**Run tests:**
```bash
uv run python -m pytest tests/
```

---

## Environment Variables

```env
# Path to master skill list Excel file
EXCEL_SKILL_GAP=data/skills_master.xlsx

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# Redis
REDIS_URL=rediss://default:your_password@your-endpoint.upstash.io:6379
REDIS_MAX_RETRIES=3
REDIS_JOB_QUEUE_PREFIX=jobs
REDIS_PROCESSED_TTL=86400

# Scraping limits
JOB_SCRAPING_MAX_PAGES_PER_BOARD=2
JOB_SCRAPING_MAX_JOBS_PER_BOARD=50
JOB_SCRAPING_DOWNLOAD_DELAY=2.0

# Days after which a scraped job is considered stale and deleted
JOB_STALE_AFTER_DAYS=7

# Roles to scrape (JSON array or comma-separated)
PERMITTED_ROLES=["Backend Developer", "Data Engineer", "Software Engineer"]
```

---

## Project Structure

```
main.py                    <- entry point: runs full pipeline for all permitted roles
pyproject.toml             <- dependencies (managed with uv)
.env.example               <- environment variable template
data/
  skills_master.xlsx       <- master skill list used by the enricher
core/
  settings.py              <- env-backed settings singleton
  state.py                 <- AgentState and JobData TypedDicts
  role_filters.py          <- role allowlist enforcement helpers
scraper/
  spider.py                <- multi-board scrape coordinator (JobScraperSpider)
  boards/
    base.py                <- BaseJobParser ABC with shared utilities
    linkedin.py            <- LinkedIn parser
    indeed.py              <- Indeed parser
    rozee.py               <- Rozee.pk parser
    mustakbil.py           <- Mustakbil parser
pipeline/
  enricher.py              <- JobEnricher: description cleaning, skill/experience/salary extraction
  enricher_node.py         <- LangChain node wrapper around JobEnricher
  scout.py                 <- digital_scout_node: query-driven scraping with role guard
services/
  redis.py                 <- Redis queue and deduplication service
  supabase.py              <- Supabase CRUD operations
tests/
  test_scout.py            <- query-intent validation tests for digital_scout_node
```
