import sqlite3
import time
import random
import re
from statistics import mean
from selenium import webdriver
from selenium.webdriver.common.by import By
driver = webdriver.Chrome() 

# --- CONFIGURATION ---
DB_PATH = "gpus.db"
TABLE_NAME = "gpus"

# --- DATABASE SETUP ---
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 1. Add Column (Safe Mode)
try:
    cursor.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN amazon_new_avg REAL")
    print(f"Column 'amazon_new_avg' added.")
except sqlite3.OperationalError:
    pass # Column already exists, proceed.

# 2. RESET PRICES TO NULL
print("Resetting Amazon prices to NULL...")
cursor.execute(f"UPDATE {TABLE_NAME} SET amazon_new_avg = NULL")
conn.commit()

# --- FUNCTIONS ---

def get_price_float(price_str):
    try:
        clean_str = re.sub(r'[^\d.]', '', price_str)
        return float(clean_str)
    except ValueError:
        return None

def scrape_amazon_avg(driver, search_term):
    try:
        query = f"{search_term} graphics card"
        encoded_query = query.replace(" ", "+")
        url = f"https://www.amazon.com/s?k={encoded_query}"
        
        
        driver.get(url)
        time.sleep(random.uniform(10, 15))
        
        if "api-services-support@amazon.com" in driver.page_source:
            print("  Amazon CAPTCHA detected! Skipping...")
            return None # Return None instead of 0.0 so we don't save bad data

        prices = []
        
        # FIX: Find the RESULT ITEM containers first, not just prices
        # This allows us to check if the text says "Renewed"
        items = driver.find_elements(By.CSS_SELECTOR, "div.s-result-item[data-component-type='s-search-result']")
        
        for item in items:
            # Check for text inside the item (Title usually)
            full_text = item.text.lower()
            
            # FILTER: Skip Refurbished/Renewed stuff
            if "renewed" in full_text or "refurbished" in full_text:
                continue

            if "sponsored" in full_text:
                continue

            search_words = search_term.lower().split()
            if not all(word in full_text for word in search_words if word not in ["geforce", "radeon", "nvidia", "amd"]):
                 continue
            
            # If it's clean, try to find the price inside THIS item
            try:
                price_element = item.find_element(By.CSS_SELECTOR, ".a-price .a-offscreen")
                price_text = price_element.get_attribute("textContent")
                prices.append(get_price_float(price_text))
            except:
                continue # No price on this item, move to next
            
            if len(prices) >= 5:
                break
                
        if not prices:
            return None
            
        return round(mean(prices), 2)

    except Exception as e:
        print(f"  Error scraping Amazon: {e}")
        return None

# --- MAIN LOOP ---

# Select all GPUs (Because we just set them all to NULL)
cursor.execute(f"SELECT name FROM {TABLE_NAME}")
rows = cursor.fetchall()
gpu_names = [r[0] for r in rows]

print(f"Found {len(gpu_names)} GPUs to update.")

for i, name in enumerate(gpu_names):
    print(f"[{i+1}/{len(gpu_names)}] Processing: {name}")
    
    amazon_price = scrape_amazon_avg(driver, name)
    
    if amazon_price is not None:
        print(f"  -> Amazon Avg (New): ${amazon_price}")
        
        # Only update if we actually found a price
        cursor.execute(f"UPDATE {TABLE_NAME} SET amazon_new_avg = ? WHERE name = ?", (amazon_price, name))
        conn.commit()
    else:
        print(f"  -> No valid prices found (or CAPTCHA). Keeping as NULL.")
    
    # Sleep
    sleep_time = random.uniform(10, 15)
    time.sleep(sleep_time)

conn.close()
driver.quit()
print("Pricing update complete.")