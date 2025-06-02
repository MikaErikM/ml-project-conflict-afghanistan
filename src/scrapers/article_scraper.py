import json
import requests
from bs4 import BeautifulSoup
import logging
import os
import argparse
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# Configure logging
logging.basicConfig(
   filename='english_article_processing.log',
   level=logging.INFO,
   format='%(asctime)s - %(levelname)s - %(message)s'
)

# File paths
CHECKPOINT_FILE = 'english_processed_articles.txt'
DEBUG_FOLDER = 'debug'
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
INPUT_FILE_PATH = os.path.join(BASE_DIR, 'links', 'alemarahenglish_articles.json')

# Retry settings
MAX_RETRIES = 5
INITIAL_BACKOFF = 1
BACKOFF_MULTIPLIER = 2
MAX_BACKOFF = 60

# Parallel processing settings
MAX_WORKERS = 10  
BATCH_DELAY = 0.5
CHECKPOINT_FREQUENCY = 100

# Global set to track processed URLs
PROCESSED_URLS = set()

def load_processed_links():
   """Load links of already processed articles from the checkpoint file."""
   processed_links = set()
   if os.path.exists(CHECKPOINT_FILE):
       try:
           with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as file:
               for line in file:
                   processed_links.add(line.strip())
       except Exception as e:
           logging.error(f"Error loading checkpoint file: {e}. Starting from scratch.")
           return set()
   return processed_links

def save_processed_links(links_to_save):
   """Append the list of processed links to the checkpoint file."""
   try:
       with open(CHECKPOINT_FILE, 'a', encoding='utf-8') as file:
           for link in links_to_save:
               file.write(link + '\n')
   except Exception as e:
       logging.error(f"Error saving checkpoint file: {e}")

def save_debug_html(url, html_content):
   """Save the HTML content of a webpage for debugging purposes."""
   if not os.path.exists(DEBUG_FOLDER):
       os.makedirs(DEBUG_FOLDER)
   filename = url.replace("https://", "").replace("/", "_").replace("%", "_") + ".txt"
   debug_file_path = os.path.join(DEBUG_FOLDER, filename)
   with open(debug_file_path, 'w', encoding='utf-8') as file:
       file.write(html_content)
   logging.info(f"Saved debug HTML to {debug_file_path}.")

def fetch_html_with_retries(url):
   """Fetch the HTML content of a given URL with retries and exponential backoff."""
   headers = {
       'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
   }
   backoff = INITIAL_BACKOFF
   for attempt in range(1, MAX_RETRIES + 1):
       try:
           logging.info(f"Attempt {attempt}: Fetching URL {url}")
           response = requests.get(url, headers=headers, timeout=10)
           response.raise_for_status()
           response.encoding = 'utf-8'
           return response.text
       except requests.exceptions.RequestException as e:
           logging.warning(f"Attempt {attempt} failed for URL {url}: {e}")
           if attempt == MAX_RETRIES:
               logging.error(f"Max retries reached. Failed to fetch URL: {url}")
               return None
           wait_time = min(backoff, MAX_BACKOFF) + random.uniform(0, 1)
           logging.info(f"Retrying in {wait_time:.2f} seconds...")
           time.sleep(wait_time)
           backoff *= BACKOFF_MULTIPLIER

def extract_article_data(html_content):
   """Extract title, lead, body, and metadata from the article's HTML content."""
   soup = BeautifulSoup(html_content, 'html.parser')
   article_data = {}

   # Extract the title
   title_element = soup.select_one('h1.post-title a')
   article_data['title'] = title_element.text.strip() if title_element else None

   # Extract the lead
   lead_element = soup.select_one('div.lead p')
   article_data['lead'] = lead_element.text.strip() if lead_element else None

   # Extract the body
   body_element = soup.select_one('div.entry')
   if body_element:
       body_paragraphs = [p.text.strip() for p in body_element.find_all('p')]
       article_data['body'] = "\n\n".join(body_paragraphs)
   else:
       article_data['body'] = None

   # Extract metadata
   metadata = {}
   
   # Extract categories from breadcrumb
   breadcrumb_element = soup.select_one('div.breadcrumb div.nhi')
   if breadcrumb_element:
       categories = [a.text.strip() for a in breadcrumb_element.find_all('a')[1:]]  # Skip "Home"
       metadata['categories'] = categories

   # Extract publish date and views
   breadcrumb_list = soup.select('div.breadcrumb li')
   for item in breadcrumb_list:
       text = item.text.strip()
       if 'publish :' in text:
           metadata['publication_date'] = text.split('publish :')[-1].strip()
       elif 'View :' in text:
           metadata['views'] = text.split('View :')[-1].strip()

   # Extract image URL if present
   thumbnail_element = soup.select_one('div.thumbnail img')
   if thumbnail_element and thumbnail_element.get('src'):
       metadata['image_url'] = thumbnail_element['src']

   # Extract tags
   tags_container = soup.select_one('div.im-tag-items')
   if tags_container:
       no_tags_element = tags_container.select_one('p')
       if no_tags_element and "there is no tags in this article" in no_tags_element.text:
           metadata['tags'] = []
       else:
           tags = [tag.text.strip() for tag in tags_container.find_all('a')]
           metadata['tags'] = tags
   else:
       metadata['tags'] = []

   article_data['metadata'] = metadata
   return article_data

def process_urls_in_batches(url_list, test_mode=False):
   """Process URLs in parallel batches using ThreadPoolExecutor with checkpointing."""
   global PROCESSED_URLS
   extracted_data = []
   batch_count = 0
   processed_count = 0
   links_to_save = []

   # Filter out already processed URLs
   url_list = [url for url in url_list if url not in PROCESSED_URLS]
   
   for i in tqdm(range(0, len(url_list)), desc="Overall Progress"):
       batch = url_list[i:i + MAX_WORKERS]
       logging.info(f"Processing batch {batch_count + 1} with {len(batch)} URLs.")
       batch_count += 1

       with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
           future_to_url = {executor.submit(fetch_html_with_retries, url): url for url in batch}
           
           for future in as_completed(future_to_url):
               url = future_to_url[future]
               try:
                   if url not in PROCESSED_URLS:
                       html_content = future.result()
                       if html_content:
                           article_data = extract_article_data(html_content)
                           article_data['link'] = url
                           extracted_data.append(article_data)
                           links_to_save.append(url)
                           processed_count += 1
                           PROCESSED_URLS.add(url)
               except Exception as e:
                   logging.error(f"Error processing URL {url}: {e}")
                   
       if processed_count >= CHECKPOINT_FREQUENCY or i + MAX_WORKERS >= len(url_list):
           if not test_mode:
               save_processed_links(links_to_save)
           links_to_save = []
           processed_count = 0
           logging.info(f"Checkpoint saved. Total processed URLs: {len(load_processed_links())}")

       time.sleep(BATCH_DELAY)

   return extracted_data

def process_articles(input_file, test_mode=False, test_limit=None):
   """Process articles from the input JSON file, extracting relevant data."""
   global PROCESSED_URLS
   processed_links = load_processed_links()
   PROCESSED_URLS.update(processed_links)
   logging.info(f"Loaded {len(processed_links)} processed links from checkpoint.")
   extracted_data = []

   try:
       with open(input_file, 'r', encoding='utf-8') as file:
           articles = json.load(file)
   except FileNotFoundError:
       logging.error(f"Input file not found: {input_file}")
       return

   url_list = [
       article_info['link'] for article_info in articles
       if article_info.get('link') and article_info['link'] not in PROCESSED_URLS
   ]

   if test_mode and test_limit:
       url_list = url_list[:test_limit]

   logging.info(f"Starting to process {len(url_list)} articles.")
   extracted_data = process_urls_in_batches(url_list, test_mode)

   output_filename = "english_extracted_articles.json"
   with open(output_filename, 'w', encoding='utf-8') as outfile:
       json.dump(extracted_data, outfile, indent=4, ensure_ascii=False)
   logging.info(f"Extracted data saved to '{output_filename}'.")

if __name__ == "__main__":
   parser = argparse.ArgumentParser(description="Process English articles from a JSON file.")
   parser.add_argument("--test", action="store_true", help="Run in test mode (processes a limited number of articles).")
   parser.add_argument("--limit", type=int, help="Number of articles to process in test mode.", default=2)
   args = parser.parse_args()

   process_articles(INPUT_FILE_PATH, test_mode=args.test, test_limit=args.limit if args.test else None)