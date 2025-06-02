import requests
from bs4 import BeautifulSoup
import json
import logging
import os
from tqdm import tqdm
import time

# Configure logging
logging.basicConfig(filename='alemarahenglish_scraper.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

DEBUG_FOLDER = "debug"
OUTPUT_JSON_FILE = "alemarahenglish_articles.json"

def scrape_alemarahenglish(start_page=1, end_page=5):
    """
    Scrapes articles from the al-Emarah English website and appends results to JSON.
    """
    base_url = "https://www.alemarahenglish.af/"
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'de-DE,de;q=0.9,en-GB;q=0.8,en;q=0.7,en-US;q=0.6',
        'cookie': 'cf_clearance=F_C4m_Z9NoAN7nYu4EwLKyhQ_Yq3R4b3rsRfDicj6rI-1735520253-1.2.1.1-f65ilWo6j9XLcjJHZwXVK962NhDK7tz7a8ZBxSP_ynxeOxOKtuU.MOw4LLXeiyxP9pCqwHxRCLE_3Tv159k3.9SY_CDX6Jz.5oxVsyCz3xHSwx4s4TuRwqTmkH7v4OHFHnxPst2c82Doc.wG34YbnJR.25CtIE_1NBpZxVoRT0leTRfhPAqHvo0HMY.XtvQRvIYKRqva2Kp9DRFa35par6vij3gxikZipVJnEaE8CdqXg7CoICRF5XM5o0Uxiy1g3pZXHrAKgdMDOTKITHaNSzcvTnNbbQmFcSJcHbsSzQXVzEVHIhNy7_Bb7yfc1hFb7DY0fvujPCbbAKIivOdArPNbVW4F20F93x8XuMb.DlTy8p8hmZit2UYZuQNmWJOhFMTx9ckby.Au7css6BjjMdRLgfJv8Mx6JxdDiMT8rBYot45rcG_0pL.OZYj9fxMj6UIbMpdRXXUna9Ced.PMXA',
        'priority': 'u=0, i',
        'referer': 'https://www.alemarahenglish.af/',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-arch': '"arm"',
        'sec-ch-ua-bitness': '"64"',
        'sec-ch-ua-full-version': '"131.0.6778.205"',
        'sec-ch-ua-full-version-list': '"Google Chrome";v="131.0.6778.205", "Chromium";v="131.0.6778.205", "Not_A Brand";v="24.0.0.0"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-model': '""',
        'sec-ch-ua-platform': '"macOS"',
        'sec-ch-ua-platform-version': '"13.0.1"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    }

    if not os.path.exists(DEBUG_FOLDER):
        os.makedirs(DEBUG_FOLDER)
        logging.info(f"Created debug folder: {DEBUG_FOLDER}")

    for page_num in tqdm(range(start_page, end_page + 1), desc="Scraping English Pages"):
        url = f"{base_url}page/{page_num}/" if page_num > 1 else base_url
        logging.info(f"Fetching English page: {url}")
        articles_on_page = []
        
        # Add retry logic
        max_retries = 3
        retry_delay = 5  # seconds
        
        for retry_count in range(max_retries):
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                polist_div = soup.select_one('body > div:nth-child(6) > div > section > div.main_content.clearfix > div.inn_top.clearfix > div > div.main-news.clearfix > div.polist')

                if polist_div:
                    logging.info(f"Found 'polist' div on English page {page_num}")
                    items = polist_div.select('div.item')
                    logging.info(f"Found {len(items)} items on English page {page_num}")
                    for item in items:
                        try:
                            title_tag = item.select_one('h2 a')
                            title = title_tag.text.strip()
                            link = title_tag['href']
                            date_tag = item.select_one('div.mydate b')
                            date = date_tag.text.strip() if date_tag else None
                            articles_on_page.append({"title": title, "link": link, "date": date})
                        except AttributeError as e:
                            logging.error(f"Error extracting data from item on English page {page_num}: {e}")
                else:
                    logging.warning(f"Could not find 'polist' div on English page {page_num}")
                
                # If we get here without error, break out of the retry loop
                break
                
            except requests.exceptions.RequestException as e:
                if retry_count < max_retries - 1:
                    logging.warning(f"Error fetching English page {page_num} (attempt {retry_count + 1}/{max_retries}): {e}. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    # Increase delay for next attempt (exponential backoff)
                    retry_delay *= 2
                else:
                    logging.error(f"Failed to fetch English page {page_num} after {max_retries} attempts: {e}")
            except AttributeError as e:
                if retry_count < max_retries - 1:
                    logging.warning(f"Error parsing English page {page_num} (attempt {retry_count + 1}/{max_retries}): {e}. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    # Increase delay for next attempt (exponential backoff)
                    retry_delay *= 2
                else:
                    logging.error(f"Failed to parse English page {page_num} after {max_retries} attempts: {e}")

        if articles_on_page:
            save_as_json_append(articles_on_page, filename=OUTPUT_JSON_FILE)
            logging.info(f"Appended {len(articles_on_page)} articles from English page {page_num} to {OUTPUT_JSON_FILE}")

def save_as_json_append(new_data, filename):
    """Appends new data to an existing JSON file or creates a new one."""
    filepath = filename
    try:
        with open(filepath, 'r+', encoding='utf-8') as f:
            try:
                existing_data = json.load(f)
            except json.JSONDecodeError:
                existing_data = []
            existing_data.extend(new_data)
            f.seek(0)
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
            f.truncate()
    except FileNotFoundError:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(new_data, f, ensure_ascii=False, indent=2)
    logging.info(f"Appended data to {filepath}")

def clear_json_file(filename):
    """Clears the content of the JSON output file."""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("[]")
    logging.info(f"Cleared the content of {filename}")

def test_scraper_english():
    """Tests the scraper on a small range of English pages."""
    logging.info("Running scraper test for English website...")
    clear_json_file(filename=OUTPUT_JSON_FILE)
    scrape_alemarahenglish(start_page=1, end_page=2)
    logging.info(f"Test scrape for English website completed. Check {OUTPUT_JSON_FILE}")

if __name__ == "__main__":
    #test_scraper_english()

    # To scrape all English pages, uncomment the following:
    clear_json_file(filename=OUTPUT_JSON_FILE)
    scrape_alemarahenglish(start_page=1, end_page=2525)
    logging.info(f"Scraping for English website completed. Check {OUTPUT_JSON_FILE}")