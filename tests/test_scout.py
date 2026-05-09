"""
Unit tests for Digital Scout query-intent validation.

These tests ensure the scraper rejects non-job intent queries before hitting
external scraping infrastructure.
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.scout import digital_scout_node
from langchain_core.messages import HumanMessage


class TestScoutQueryValidation(unittest.TestCase):
    def test_rejects_non_job_query_and_skips_scraping(self):
        state = {
            "messages": [HumanMessage(content="Find me cats in Lahore for adoption")],
            "user_id": "test_user_123",
            "user_profile": None,
            "search_query": "Find me cats in Lahore for adoption",
            "raw_job_list": [],
            "scraping_status": "pending",
            "current_page": 1,
            "vetted_jobs": [],
            "target_job": None,
            "optimized_materials": None,
            "human_approval": None,
            "error": None,
            "retry_count": 0,
        }

        spider_mock = Mock()
        redis_mock = Mock()
        supabase_mock = Mock()

        with patch("pipeline.scout.get_spider", return_value=spider_mock), patch(
            "pipeline.scout.get_redis_service", return_value=redis_mock
        ), patch("pipeline.scout.get_supabase_service", return_value=supabase_mock):
            result = digital_scout_node(state)

        self.assertEqual(result.get("scraping_status"), "failed")
        self.assertEqual(result.get("raw_job_list"), [])
        self.assertTrue(result.get("error"))
        self.assertIn("does not look like a job search", result.get("error").lower())

        spider_mock.scrape_all_boards.assert_not_called()
        redis_mock.is_job_processed.assert_not_called()
        supabase_mock.bulk_insert_jobs.assert_not_called()

    def test_allows_valid_job_query(self):
        state = {
            "messages": [HumanMessage(content="Find AI engineer jobs in Lahore")],
            "user_id": "test_user_123",
            "user_profile": None,
            "search_query": "Find AI engineer jobs in Lahore",
            "raw_job_list": [],
            "scraping_status": "pending",
            "current_page": 1,
            "vetted_jobs": [],
            "target_job": None,
            "optimized_materials": None,
            "human_approval": None,
            "error": None,
            "retry_count": 0,
        }

        fake_jobs = [
            {
                "job_id": "job_1",
                "title": "AI Engineer",
                "company": "Acme",
                "location": "Lahore",
                "job_url": "https://example.com/job/1",
                "board": "indeed",
                "description": "Build data pipelines",
                "skills": ["python", "sql"],
                "posted_date": None,
                "salary": None,
                "employment_type": "full-time",
                "experience_required": None,
                "raw_html": "",
            }
        ]

        spider_mock = Mock()
        spider_mock.scrape_all_boards.return_value = fake_jobs

        redis_mock = Mock()
        redis_mock.is_job_processed.return_value = False

        supabase_mock = Mock()
        supabase_mock.bulk_insert_jobs.return_value = True

        with patch("pipeline.scout.get_spider", return_value=spider_mock), patch(
            "pipeline.scout.get_redis_service", return_value=redis_mock
        ), patch("pipeline.scout.get_supabase_service", return_value=supabase_mock):
            result = digital_scout_node(state)

        self.assertEqual(result.get("scraping_status"), "completed")
        self.assertEqual(len(result.get("raw_job_list", [])), 1)
        spider_mock.scrape_all_boards.assert_called_once()


if __name__ == "__main__":
    unittest.main()
