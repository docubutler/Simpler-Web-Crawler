import requests

response = requests.post(
    "http://127.0.0.1:8000/crawl",
    json={"start_urls": ["https://eastel.com.my/mobile-plan/"]}
)
print(response.json())