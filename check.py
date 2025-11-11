import requests

response = requests.post(
    "http://127.0.0.1:8000/crawl",
    json={"start_urls": ["http://httpbin.org/html"], "allowed_domains": ["httpbin.org"]}
)
print(response.json())