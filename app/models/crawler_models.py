
from pydantic import BaseModel
from typing import List

class CrawlRequest(BaseModel):
    start_urls: List[str]
    allowed_domains: List[str]

class CrawlResult(BaseModel):
    url: str
    html: str

class CrawlResponse(BaseModel):
    status: str
    results: List[CrawlResult]

class RefreshResourcesResponse(BaseModel):
    status: str
    message: str
