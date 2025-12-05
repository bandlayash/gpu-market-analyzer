from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import random
import sqlite3

# --- DATABASE SETUP ---
db_path = "gpus.db"
table_name = "gpus"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Add new columns if they don't exist
new_columns = ["tdp", "base_clock", "driver_support"]
for col in new_columns:
    try:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col} TEXT")
        print(f"Column '{col}' added.")
    except sqlite3.OperationalError:
        print(f"Column '{col}' already exists.")
conn.commit()

# --- HELPER FUNCTION ---
def clean_gpu_name(scraped_name):
    name = scraped_name.replace(" Specs", "").strip()
    vendors = ["NVIDIA ", "AMD ", "Intel ", "ATI "]
    for vendor in vendors:
        if name.startswith(vendor):
            name = name.replace(vendor, "", 1)
            break
    return name.strip()

# --- SELENIUM SETUP ---
driver = webdriver.Chrome()
driver.get("https://www.techpowerup.com/gpu-specs/")
links = []

print("Collecting links...")
rows = driver.find_elements(By.XPATH, "//table[.//th[contains(text(), 'Name')]]//tr")

for row in rows:
    try:
        link_element = row.find_element(By.XPATH, ".//td[1]//a")
        url = link_element.get_attribute("href")
        if url:
            links.append(url)
    except:
        continue

links = list(set(links))
print(f"Found {len(links)} links. Starting scrape...")

# --- SCRAPING & UPDATING ---
for index, link in enumerate(links):
    try:
        driver.get(link)
        time.sleep(random.uniform(10, 15))

        # 1. Scrape New Fields
        tdp = "N/A"
        base_clock = "N/A"
        driver_support = "N/A"

        try:
            # TDP
            tdp_el = driver.find_element(By.XPATH, "//dt[contains(text(), 'TDP')]/following-sibling::dd[1]")
            tdp = tdp_el.text.strip()
        except:
            pass

        try:
            # Base Clock
            clock_el = driver.find_element(By.XPATH, "//dt[contains(text(), 'Base Clock')]/following-sibling::dd[1]")
            base_clock = clock_el.text.strip()
        except:
            pass
            
        try:
            # Driver Support
            support_el = driver.find_element(By.XPATH, "//dt[contains(text(), 'Driver Support')]/following-sibling::dd[1]")
            driver_support = support_el.text.strip()
        except:
            pass

        # 2. Get Name for Matching
        full_title = driver.title.split('|')[0].strip()
        db_name = clean_gpu_name(full_title)

        print(f"[{index + 1}/{len(links)}] {db_name}")
        print(f"   -> TDP: {tdp} | Clock: {base_clock} | Support: {driver_support}")

        # 3. Update Database
        cursor.execute(f"""
            UPDATE {table_name} 
            SET tdp = ?, base_clock = ?, driver_support = ?
            WHERE name = ?
        """, (tdp, base_clock, driver_support, db_name))
        
        conn.commit()

    except Exception as e:
        print(f"Error scraping {link}: {e}")

conn.close()
driver.quit()
print("Done.")