import requests
import json
import time

# --- Configuration ---
# Match the host and port used in web-crawler.py
API_URL = "http://127.0.0.1:8000/crawl" 

# --- Sample Payload ---
# NOTE: Replace these with actual URLs you want to test!
# The crawler will scrape the start URL and then any links on that page 
# that belong to the allowed_domains.
SAMPLE_PAYLOAD = {
    "start_urls": ["http://toscrape.com/"],
    "allowed_domains": ["toscrape.com", "example.com"]
}

def test_crawl_endpoint():
    """Sends a POST request to the /crawl endpoint and prints the results."""
    print(f"--- Testing {API_URL} ---")
    print(f"Payload: {json.dumps(SAMPLE_PAYLOAD, indent=4)}\n")
    
    start_time = time.time()
    
    try:
        # Send the POST request
        response = requests.post(
            API_URL, 
            json=SAMPLE_PAYLOAD, 
            timeout=60 # Set a generous timeout for the crawl process
        )
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

        end_time = time.time()
        response_data = response.json()

        print(f"Status Code: {response.status_code}")
        print(f"Total Time Taken: {end_time - start_time:.2f} seconds")
        print("-" * 50)
        
        # Check if the status is 'finished' and display the results
        if response_data.get("status") == "finished":
            results = response_data.get("results", [])
            num_results = len(results)
            print(f"Crawl Status: SUCCESS ({num_results} result(s) found)")
            
            if num_results > 0:
                print("\n--- Sample Scraped Data (First Item HTML Snippet) ---")
                
                # To avoid printing massive HTML, we show a snippet
                first_html_snippet = results[0].get('html', 'No HTML found').strip()
                
                # Truncate the HTML output for readability
                max_length = 500 
                truncated_html = first_html_snippet[:max_length] + ("..." if len(first_html_snippet) > max_length else "")
                
                print(f"URL: {results[0].get('url', 'N/A')}")
                print(f"HTML: {truncated_html}")

            else:
                print("No content was scraped (results array is empty).")

        else:
            # Handle error status returned by the FastAPI app
            print(f"Crawl Status: ERROR")
            print(f"Server Message: {response_data.get('message', 'No error message provided.')}")

    except requests.exceptions.ConnectionError:
        print(f"\nERROR: Could not connect to the API server at {API_URL}.")
        print("Please ensure your 'web-crawler.py' server is running.")
    except requests.exceptions.RequestException as e:
        print(f"\nAn error occurred during the request: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    test_crawl_endpoint()