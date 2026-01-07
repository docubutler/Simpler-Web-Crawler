
from fastapi import APIRouter, Body
from app.services.crawler_service import crawl_service, refresh_resources_service
from app.models.crawler_models import CrawlRequest, CrawlResponse, RefreshResourcesResponse

router = APIRouter()

@router.post("/crawl", response_model=CrawlResponse)
async def crawl_endpoint(request: CrawlRequest = Body(...)):
    """
    Runs the Scrapy crawl using the global ProcessPoolExecutor.
    """
    results = await crawl_service(request.start_urls, request.allowed_domains)
    return results

@router.post("/refresh_resources", response_model=RefreshResourcesResponse)
async def refresh_resources_endpoint():
    """
    Properly shuts down the worker pool and the manager, and re-initializes them.
    This fixes resource leaks without stopping the main FastAPI server.
    """
    response = await refresh_resources_service()
    return response
