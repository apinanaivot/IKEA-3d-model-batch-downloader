import os
import sys
import requests
from bs4 import BeautifulSoup
import json
import sqlite3
import re
from tqdm import tqdm
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging

# Suppress unnecessary logging
logging.getLogger('WDM').setLevel(logging.NOTSET)
os.environ['WDM_LOG_LEVEL'] = '0'

# Create downloads directory
download_dir = 'downloaded-files'
os.makedirs(download_dir, exist_ok=True)

# Set up SQLite database
conn = sqlite3.connect('ikea_products.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS products
             (url TEXT PRIMARY KEY, name TEXT, color TEXT, glb_url TEXT, downloaded INTEGER)''')

def get_chrome_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--log-level=3')  # Only show fatal errors
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    try:
        # Try with log_level argument
        service = Service(ChromeDriverManager(log_level=0).install())
    except TypeError:
        # If log_level is not supported, use without it
        service = Service(ChromeDriverManager().install())
    
    # Redirect stderr to devnull to suppress remaining messages
    original_stderr = sys.stderr
    sys.stderr = open(os.devnull, 'w')
    
    driver = webdriver.Chrome(service=service, options=options)
    
    # Restore stderr
    sys.stderr = original_stderr
    
    return driver

def get_product_links(url):
    driver = get_chrome_driver()
    try:
        driver.get(url)
        
        # Wait for the product grid to load
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.plp-fragment-wrapper'))
        )
        
        # Scroll to load all products
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # Wait for page to load
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        
        # Wait for all product links to be present
        WebDriverWait(driver, 30).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.plp-fragment-wrapper a.plp-product__image-link'))
        )
        
        links = [link.get_attribute('href') for link in driver.find_elements(By.CSS_SELECTOR, '.plp-fragment-wrapper a.plp-product__image-link')]
        
        print(f"Found {len(links)} products on this page")
        return list(set(links))  # Remove duplicates
    except TimeoutException:
        print(f"Timeout while loading products on page: {url}")
        return []
    except Exception as e:
        print(f"Error while getting product links from {url}: {str(e)}")
        return []
    finally:
        driver.quit()

def get_color_variant_links(url, download_all_colors):
    if not download_all_colors:
        return [url]
    
    driver = get_chrome_driver()
    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.js-product-style-picker'))
        )
        
        variants = [url]  # Include the original URL
        style_picker = driver.find_element(By.CSS_SELECTOR, '.js-product-style-picker')
        if style_picker:
            variant_links = style_picker.find_elements(By.CSS_SELECTOR, '.pip-product-styles__link')
            for link in variant_links:
                variants.append(link.get_attribute('href'))
        
        return variants
    finally:
        driver.quit()

def get_product_details(url):
    driver = get_chrome_driver()
    try:
        driver.get(url)
        
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, 'title'))
        )
        
        title = driver.title
        if title:
            full_title = title.strip()
            name_color = full_title.split(' - IKEA')[0]
            match = re.match(r'(.*?),\s*(.*)', name_color)
            if match:
                name, color = match.groups()
            else:
                name = name_color
                color = "Default"
        else:
            name = "Unknown"
            color = "Unknown"
        
        try:
            script = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, 'pip-xr-viewer-model'))
            )
            if script:
                try:
                    data = json.loads(script.get_attribute('innerHTML'))
                    glb_url = data.get('url')
                    return name, color, glb_url
                except json.JSONDecodeError:
                    print(f"Error decoding JSON for {url}")
        except TimeoutException:
            print(f"GLB model script not found for {url}")
        
    except TimeoutException:
        print(f"Timeout while loading page: {url}")
    except Exception as e:
        print(f"Error processing {url}: {str(e)}")
    finally:
        driver.quit()
    
    return name, color, None

def download_glb(url, filename):
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    
    with open(filename, 'wb') as f, tqdm(
        desc=filename,
        total=total_size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024,
    ) as progress_bar:
        for data in response.iter_content(chunk_size=1024):
            size = f.write(data)
            progress_bar.update(size)

def process_product(url, download_all_colors):
    print(f"\nProcessing product: {url}")
    
    # Check if the main URL has been processed
    c.execute("SELECT * FROM products WHERE url=?", (url,))
    if c.fetchone():
        print(f"Skipping already processed product: {url}")
        return

    try:
        variant_urls = get_color_variant_links(url, download_all_colors)
        print(f"Found {len(variant_urls)} color variants")
        
        for variant_url in variant_urls:
            c.execute("SELECT * FROM products WHERE url=?", (variant_url,))
            if c.fetchone():
                print(f"Skipping already processed variant: {variant_url}")
                continue

            name, color, glb_url = get_product_details(variant_url)
            print(f"Processing variant: {name} - {color}")
            
            if glb_url:
                filename = f"{name} - {color}.glb"
                filename = re.sub(r'[<>:"/\\|?*]', '', filename)  # Remove invalid characters
                full_path = os.path.join(download_dir, filename)
                download_glb(glb_url, full_path)
                downloaded = 1
            else:
                downloaded = 0
                print(f"No GLB file found for {name} - {color}")

            c.execute("INSERT INTO products VALUES (?, ?, ?, ?, ?)",
                      (variant_url, name, color, glb_url, downloaded))
            conn.commit()
    except Exception as e:
        print(f"Error processing product {url}: {str(e)}")

def main():
    start_url = input("Enter the IKEA category URL to download products from: ")
    download_all_colors = input("Do you want to download all color variants? (y/n): ").lower() == 'y'
    
    page = 1
    total_processed = 0
    
    while True:
        print(f"\nFetching product links from page {page}")
        current_url = f"{start_url}{'&' if '?' in start_url else '?'}page={page}"
        product_links = get_product_links(current_url)
        
        if not product_links:
            print(f"No products found on page {page}. Finishing process.")
            break

        for i, link in enumerate(product_links, 1):
            print(f"\nProcessing item {i} of {len(product_links)} on page {page}")
            process_product(link, download_all_colors)
            total_processed += 1

        print(f"Completed page {page}. Total products processed so far: {total_processed}")
        page += 1

    conn.close()
    print(f"Finished processing all pages. Total products processed: {total_processed}")

if __name__ == "__main__":
    main()