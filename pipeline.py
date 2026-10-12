"""AI-Powered Assistant & Automation Pipeline.

Orchestrates:
1. Web Scraping with headless Chrome & Selenium.
2. AI Extraction with Google Gemini using Pydantic Structured Outputs.
3. Persistence to SQLite database with parameterized queries.
4. Exporting structured outputs to JSON.
5. Graceful exception recovery, retry backoff, and logging.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Dict, Optional

from ai_service.gemini_client import GeminiExtractionService
from config import PipelineConfig, default_config, logger
from scraper.selenium_pipeline import SeleniumPipelineScraper
from storage.db_handler import DatabaseHandler


def print_banner() -> None:
    """Displays standard pipeline header."""
    banner = """
======================================================================
     AI-POWERED ASSISTANT & AUTOMATION PIPELINE (Gemini + Selenium)
======================================================================
"""
    print(banner)


def run_pipeline(
    target_url: Optional[str] = None,
    dry_run: bool = False,
    headless: Optional[bool] = None,
    export_json_path: Optional[str] = None,
    config: Optional[PipelineConfig] = None,
) -> Dict[str, Any]:
    """Executes the end-to-end automation pipeline.

    Args:
        target_url: URL to scrape (defaults to config default).
        dry_run: If True or if no API key is present, uses simulated structured extraction.
        headless: Override headless browser setting if provided.
        export_json_path: Custom path for exported JSON.
        config: Pipeline configuration object.

    Returns:
        Dictionary containing execution summary and record ID.
    """
    cfg = config or default_config
    if headless is not None:
        cfg.headless_browser = headless

    url_to_scrape = target_url or cfg.default_target_url
    logger.info(">>> Starting Pipeline Execution <<<")
    logger.info(f"Target URL: {url_to_scrape}")
    logger.info(f"Gemini Model: {cfg.gemini_model}")
    logger.info(f"Headless Mode: {cfg.headless_browser}")

    # Check API key status
    if not cfg.is_api_key_configured() and not dry_run:
        logger.warning(
            "Notice: GEMINI_API_KEY is not configured or is a template value. "
            "Pipeline will automatically utilize validated simulated AI extraction."
        )
        dry_run = True

    # Step 1: Scrape unstructured content via Selenium
    logger.info("[Step 1/4] Scraping web content with Selenium...")
    try:
        with SeleniumPipelineScraper(config=cfg) as scraper:
            scraped_content = scraper.scrape(url_to_scrape)
    except Exception as e:
        logger.error(f"Scraper phase encountered an error: {e}")
        raise RuntimeError(f"Pipeline failed at scraping stage: {e}") from e

    logger.info(
        f"Scraped {scraped_content.character_count} characters from '{scraped_content.page_title}'."
    )

    # Step 2: Extract structured intelligence with Gemini
    logger.info("[Step 2/4] Sending unstructured content to Gemini for Structured Extraction...")
    ai_service = GeminiExtractionService(config=cfg)
    try:
        structured_data = ai_service.extract_structured_data(
            raw_text=scraped_content.raw_text,
            source_url=scraped_content.source_url,
            force_mock=dry_run,
        )
    except Exception as e:
        logger.error(f"AI Extraction phase encountered an error: {e}")
        raise RuntimeError(f"Pipeline failed at AI extraction stage: {e}") from e

    logger.info(f"Extracted Title: '{structured_data.title}'")
    logger.info(f"Extracted {len(structured_data.categorized_topics)} topics and {len(structured_data.key_takeaways)} key takeaways.")

    # Step 3: Persist structured record into SQLite database
    logger.info("[Step 3/4] Persisting validated structured record into SQLite database...")
    db_handler = DatabaseHandler(config=cfg)
    try:
        record_id = db_handler.save_extraction(
            data=structured_data,
            source_url=scraped_content.source_url,
            raw_content_preview=scraped_content.raw_text,
        )
    except Exception as e:
        logger.error(f"Database insertion error: {e}")
        raise RuntimeError(f"Pipeline failed at database storage stage: {e}") from e

    # Step 4: Export to JSON
    logger.info("[Step 4/4] Exporting updated records to JSON file...")
    export_path = db_handler.export_to_json(export_json_path)
    logger.info(f"JSON export completed at: {export_path}")

    # Output Clean Summary
    print("\n" + "=" * 60)
    print("                    EXECUTION SUMMARY")
    print("=" * 60)
    print(f"Record ID           : {record_id}")
    print(f"Source URL          : {scraped_content.source_url}")
    print(f"Title               : {structured_data.title}")
    print(f"Summary             : {structured_data.summary}")
    print(f"Topics / Tags       : {', '.join(structured_data.categorized_topics)}")
    print("Key Takeaways       :")
    for idx, takeaway in enumerate(structured_data.key_takeaways, 1):
        print(f"  {idx}. {takeaway}")
    print(f"Sentiment           : {structured_data.analysis.sentiment} (Score: {structured_data.analysis.sentiment_score:.2f})")
    print(f"Security Risk Level : {structured_data.analysis.risk_level}")
    print(f"Security Analysis   : {structured_data.analysis.security_implications}")
    print(f"SQLite DB File      : {cfg.database_path.resolve()}")
    print(f"JSON Export File    : {export_path.resolve()}")
    print("=" * 60 + "\n")

    return {
        "record_id": record_id,
        "structured_data": structured_data.model_dump(),
        "source_url": scraped_content.source_url,
        "export_path": str(export_path),
    }


def list_records(config: Optional[PipelineConfig] = None) -> None:
    """Lists existing database records."""
    db_handler = DatabaseHandler(config=config)
    records = db_handler.fetch_all_records(limit=20)
    if not records:
        print("No records found in SQLite database.")
        return

    print(f"\n--- Stored Extraction Records ({len(records)} found) ---")
    for r in records:
        print(
            f"ID #{r['id']} | [{r['created_at'][:19]}] | {r['title']} | Risk: {r['risk_level']} | Sentiment: {r['sentiment']}"
        )
        print(f"    URL: {r['source_url']}")
        print(f"    Summary: {r['summary'][:120]}...\n")


def parse_arguments() -> argparse.Namespace:
    """Configures command line argument parser."""
    parser = argparse.ArgumentParser(
        description="AI-Powered Assistant & Automation Pipeline (Selenium + Gemini + SQLite)"
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Target webpage URL to scrape and analyze",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run Chrome in visible/headed mode instead of headless",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without calling the live Gemini API (uses simulated structured extraction)",
    )
    parser.add_argument(
        "--export-json",
        type=str,
        default=None,
        help="Custom file path for JSON export",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print stored database records and exit",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entrypoint."""
    print_banner()
    args = parse_arguments()

    if args.list:
        list_records()
        return

    try:
        run_pipeline(
            target_url=args.url,
            dry_run=args.dry_run,
            headless=False if args.no_headless else None,
            export_json_path=args.export_json,
        )
    except KeyboardInterrupt:
        logger.warning("Pipeline execution cancelled by user.")
        sys.exit(130)
    except Exception as exc:
        logger.critical(f"Pipeline terminated with fatal error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
