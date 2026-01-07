
import scrapy
import logging
from datetime import datetime
from scrapy.crawler import CrawlerProcess
import asyncio
from bs4 import BeautifulSoup

from app.main import executor, manager, init_resources

# Configure logging for this module
logger = logging.getLogger(__name__)

def extract_important_text_bs4(html_content: str) -> str:
    soup = BeautifulSoup(html_content, "lxml")
    # Remove unwanted tags
    for tag in ["script", "style", "nav", "footer", "aside", "form", "s", "a"]:
        for element in soup.find_all(tag):
            element.decompose()
    # Get visible text
    text = soup.get_text(separator="\n", strip=True)
    lines = [line for line in text.splitlines() if len(line) > 30]
    return "\n".join(lines)

class HTMLSpider(scrapy.Spider):
    name = "html_spider"
    
    custom_settings = {
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
        "CONCURRENT_REQUESTS": 16,
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 30 * 1000,
        "DEPTH_LIMIT": 2,
        "LOG_LEVEL": "INFO",
        "LOG_STDOUT": True,
    }

    def __init__(self, start_urls: list, allowed_domains: list, results: list, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = start_urls
        self.allowed_domains = allowed_domains
        self.results = results 

    def parse(self, response):
        logger.info(f"Parsing: {response.url}")
        important_text = extract_important_text_bs4(response.text)
        
        self.results.append({
            "url": response.url,
            "html": important_text
        })
        
        yield {"url": response.url, "html": important_text}

def run_crawler_process(start_urls: list, allowed_domains: list, spider_results: list) -> list:
    process = CrawlerProcess()
    try:
        process.crawl(
            HTMLSpider,
            start_urls=start_urls,
            allowed_domains=allowed_domains,
            results=spider_results
        )
        process.start(stop_after_crawl=True)
        return list(spider_results)
    except Exception as e:
        logger.error(f"Error during crawl: {e}")
        return []

async def crawl_service(start_urls: list, allowed_domains: list) -> dict:
    if executor is None or manager is None:
        logger.warning("Resources not initialized, attempting to reinitialize...")
        init_resources()
        if executor is None or manager is None:
            return {"status": "error", "message": "Server resources are not initialized. Please ensure the server started correctly.", "results": []}

    spider_results = manager.list()
    loop = asyncio.get_event_loop()
    
    try:
        results = await loop.run_in_executor(
            executor,
            run_crawler_process,
            start_urls,
            allowed_domains,
            spider_results
        )
        
        num_results = len(results)
        logger.info(f"Crawl completed. Found {num_results} result(s).")
        if num_results > 0:
            sample_urls = [r.get("url", "N/A") for r in results[:3]]
            logger.info(f"Sample URLs scraped: {", ".join(sample_urls)}")
        
        return {"status": "finished", "results": results}
    except Exception as e:
        logger.exception(f"An unexpected error occurred during crawl_service execution: {e}")
        return {"status": "error", "message": f"Crawl execution failed: {e}", "results": []}

async def refresh_resources_service() -> dict:
    global executor, manager
    
    logger.info("Shutting down existing worker pools...")
    try:
        if executor:
            executor.shutdown(wait=False, cancel_futures=True) 
            logger.info("Executor shutdown signal sent.")
    except Exception as e:
        logger.error(f"Error during executor shutdown: {e}")

    try:
        if manager:
            manager.shutdown()
            logger.info("Manager shutdown complete.")
    except Exception as e:
        logger.error(f"Error during manager shutdown: {e}")
    
    # Set globals back to None before re-init
    executor = None
    manager = None

    try:
        init_resources() 
        logger.info("Resources successfully refreshed and restarted.")
        return {"status": "refreshed_and_restarted", "message": "Worker pools have been terminated and new pools are ready for immediate use."}
    except Exception as e:
        logger.exception(f"Failed to re-initialize resources: {e}")
        return {"status": "error", "message": f"Failed to re-initialize resources: {e}"}
