import scrapy
import logging
from datetime import datetime
from scrapy.crawler import CrawlerProcess
from fastapi import FastAPI, Request
import uvicorn
import os
from dotenv import load_dotenv
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import asyncio
import sys
from contextlib import asynccontextmanager
from bs4 import BeautifulSoup
from selectolax.parser import HTMLParser

load_dotenv()

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
MAX_WORKERS = multiprocessing.cpu_count() 

# Set globals to None initially. They will be initialized safely by the startup event.
executor = None
manager = None

def init_resources():
    """Initializes the global ProcessPoolExecutor and Manager safely."""
    global executor, manager, MAX_WORKERS
    
    # Only initialize if they are currently None
    if executor is not None and manager is not None:
        return 

    print(f"Initializing ProcessPoolExecutor with {MAX_WORKERS} workers and Manager...")
    try:
        # Use a specific context to help with process pre-spawning/eager creation,
        # moving the initial startup cost to the server boot time.
        mp_context = multiprocessing.get_context('spawn')
        # max_tasks_per_child argument was added in Python 3.11. Removing it for compatibility.
        if sys.version_info >= (3, 11):
             executor = ProcessPoolExecutor(max_workers=MAX_WORKERS, mp_context=mp_context,max_tasks_per_child=1)
        else:
             executor = ProcessPoolExecutor(max_workers=MAX_WORKERS, mp_context=mp_context)

        manager = multiprocessing.Manager()
        print("Resources initialized successfully.")
    except Exception as e:
        print(f"Critical error during resource initialization: {e}")
        raise

# ignore this function - kept for reference
def extract_important_text_selectolax(html_content):
    tree = HTMLParser(html_content)
    # Remove unwanted tags
    for tag in ["script", "style", "nav", "footer", "aside", "form", "s"]:
        for node in tree.tags(tag):
            node.decompose()
    text = tree.text(separator="\n", strip=True)
    lines = [line for line in text.splitlines() if len(line) > 30]
    return "\n".join(lines)
    

def extract_important_text_bs4(html_content):
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
    
    # Note: PLAYWRIGHT_LAUNCH_OPTIONS and TWISTED_REACTOR are crucial for async operation
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
        # Keep this Scrapy-native setting to route logs to standard output
        "LOG_STDOUT": True,
    }

    def __init__(self, start_urls, allowed_domains, results, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = start_urls
        self.allowed_domains = allowed_domains
        self.results = results 

    def parse(self, response):
        print(f"Parsing: {response.url}")
        important_text = extract_important_text_bs4(response.text)
        
        # Append results to the shared list
        self.results.append({
            "url": response.url,
            "html": important_text
        })
        
        yield {"url": response.url, "html": important_text}

        # Extract and follow links (example: all <a> tags)
        # Uncomment if you want to scrap through website's hyperlinks
        # for href in response.css('a::attr(href)').getall():
        #   yield response.follow(href, self.parse)

def run_crawler(start_urls, allowed_domains, spider_results):
    process = CrawlerProcess()
    try:
        process.crawl(
            HTMLSpider,
            start_urls=start_urls,
            allowed_domains=allowed_domains,
            results=spider_results
        )
        # start(stop_after_crawl=True) blocks until the crawl is finished.
        process.start(stop_after_crawl=True)
        # Convert the managed list to a standard Python list for the return value
        return list(spider_results)
    except Exception as e:
        # Use the explicit logging for visibility
        logging.getLogger('run_crawler').error(f"Error during crawl: {e}")
        return []

# --- FastAPI Application Lifespan Handler ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles initialization (startup) and cleanup (shutdown) of resources.
    """
    # STARTUP: Initialize multiprocessing resources
    # no need to wait for user to /crawl to start each individual browser resource
    init_resources()
    
    # YIELD: Application is now ready to receive traffic
    yield
    
    # SHUTDOWN: Cleanly shut down resources
    global executor, manager
    
    print("Executing application shutdown...")
    if executor:
        print("Shutting down ProcessPoolExecutor...")
        # Use shutdown(wait=True) for a clean server shutdown
        executor.shutdown(wait=True)
    if manager:
        print("Shutting down Manager...")
        manager.shutdown()

app = FastAPI(lifespan=lifespan)


@app.post("/refresh_resources")
async def refresh_resources():
    """
    Properly shuts down the worker pool and the manager, and re-initializes them.
    This fixes resource leaks without stopping the main FastAPI server.
    """
    global executor, manager, MAX_WORKERS
    
    # --- Step 1: Shut down existing resources ---
    print("Shutting down existing worker pools...")
    try:
        if executor:
            # shutdown(wait=False) prevents blocking the FastAPI thread
            executor.shutdown(wait=False, cancel_futures=True) 
            print("Executor shutdown signal sent.")
    except Exception as e:
        print(f"Error during executor shutdown: {e}")

    try:
        if manager:
            manager.shutdown()
            print("Manager shutdown complete.")
    except Exception as e:
        print(f"Error during manager shutdown: {e}")
    
    # Set globals back to None before re-init
    executor = None
    manager = None

    # --- Step 2: Create new resources (The "Restart" part) ---
    try:
        init_resources() 
        print("Resources successfully refreshed and restarted.")
        return {"status": "refreshed_and_restarted", "message": "Worker pools have been terminated and new pools are ready for immediate use."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to re-initialize resources: {e}"}


@app.post("/crawl")
async def crawl(request: Request):
    """
    Runs the Scrapy crawl using the global ProcessPoolExecutor.
    """
    global manager, executor 

    if executor is None or manager is None:
        print("Reinitializing resources before crawl...")
        init_resources()

    # Critical check: ensure resources are initialized before use
    if executor is None or manager is None:
        return {"status": "error", "message": "Server resources are not initialized. Please ensure the server started correctly."}
        
    print(f"Received crawl request at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        data = await request.json()
    except Exception as e:
        return {"status": "error", "message": f"Invalid JSON payload: {e}"}

    start_urls = data.get("start_urls", [])
    allowed_domains = data.get("allowed_domains", [])
    
    if not start_urls:
        return {"status": "error", "message": "start_urls must be provided."}

    # Use the global manager to create the shared list
    spider_results = manager.list()

    loop = asyncio.get_event_loop()
    
    # Submit the blocking run_crawler function to the global ProcessPoolExecutor
    try:
        results = await loop.run_in_executor(
            executor,
            run_crawler,
            start_urls,
            allowed_domains,
            spider_results
        )
        
        # --- CONFIRMATION LOGGING (MAIN PROCESS) ---
        num_results = len(results)
        print(f"Crawl completed. Found {num_results} result(s).")
        if num_results > 0:
            # Print URLs of the first few scraped items for verification
            sample_urls = [r.get('url', 'N/A') for r in results[:3]]
            print(f"Sample URLs scraped: {', '.join(sample_urls)}")
        # ---------------------------------
        
        return {"status": "finished", "results": results}
    except Exception as e:
        print(f"An unexpected error occurred during execution: {e}")
        return {"status": "error", "message": f"Crawl execution failed: {e}"}


if __name__ == "__main__":
    # Check if system is Windows to apply necessary multiprocessing fixes
    if sys.platform.startswith('win'):
        # ensure process starts correctly in frozen environments
        multiprocessing.freeze_support() 
        try:
            # Force 'spawn' start method to prevent recursive spawning issues
            multiprocessing.set_start_method('spawn', force=True) 
        except RuntimeError:
            pass

    uvicorn.run("web-crawler:app", host=HOST, port=PORT, reload=False)