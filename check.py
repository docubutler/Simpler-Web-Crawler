import requests

response = requests.post(
    "http://127.0.0.1:8000/crawl",
    json={"start_urls": ["https://www.hotlink.com.my/en/products/postpaid/"]}
)
print(response.json())