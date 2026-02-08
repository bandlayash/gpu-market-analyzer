import sqlite3
import time
import random
import os
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from openai import OpenAI
from dotenv import load_dotenv

# 1. Config & Setup
load_dotenv()
api_key = os.getenv("MOONSHOT_API_KEY")

if not api_key:
    print("CRITICAL: .env file missing or MOONSHOT_API_KEY not set.")
    exit()

client = OpenAI(
    base_url='https://api.moonshot.ai/v1',
    api_key=api_key
)

DB_PATH = "gpus.db"

# 2. Initialize "Human-Like" Selenium Driver
def setup_driver():
    options = Options()
    # options.add_argument("--headless") # Comment out to see the browser working (recommended for debugging)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(options=options)
    return driver

def migrate_schema():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Ensure columns exist
    try:
        cursor.execute("ALTER TABLE gpus ADD COLUMN new_avg REAL")
    except: pass
    try:
        cursor.execute("ALTER TABLE gpus ADD COLUMN ebay_used_avg REAL")
    except: pass
    conn.commit()
    conn.close()

def get_page_text(driver, url):
    """
    Navigates to URL and extracts visible text (saving tokens vs raw HTML).
    """
    try:
        driver.get(url)
        # Random sleep to mimic reading the page
        time.sleep(random.uniform(3, 6))
        
        # Scroll down slightly to trigger lazy loading of products
        driver.execute_script("window.scrollTo(0, 400);")
        time.sleep(1)

        # Extract only the body text (cleaner for AI than raw HTML)
        body_text = driver.find_element(By.TAG_NAME, "body").text
        
        # Limit to ~15k characters (approx 3-4k tokens) to fit context
        return body_text[:15000] 
    except Exception as e:
        print(f"    [!] Selenium Error: {e}")
        return None

def analyze_new_market(gpu_model, text_data):
    """
    Sends combined text from Amz/Newegg/BB to Kimi to find the best deal.
    """
    # Filter out empty reads
    valid_data = {k: v for k, v in text_data.items() if v}
    if not valid_data: return None

    prompt = f"""
    I am looking for the BEST PRICE for a NEW "{gpu_model}".
    
    Below is text extracted from search result pages on Amazon, Newegg, and Best Buy.
    
    Task:
    1. Scan the text to find the LOWEST price for the specific card "{gpu_model}".
    2. IGNORE: Used, Refurbished, Renewed, "Open Box", "Parts Only".
    3. IGNORE: Different models (e.g. if I asked for RTX 3080, ignore RTX 3060).
    4. IGNORE: Accessories (waterblocks, fans, cables).
    5. SCAM CHECK: If price is < $50 (and not a GT 710), it's likely fake/cable/box. Ignore it.
    
    Data Source 1 (Amazon):
    {valid_data.get('amazon', 'No Data')}
    
    Data Source 2 (Newegg):
    {valid_data.get('newegg', 'No Data')}
    
    Data Source 3 (Best Buy):
    {valid_data.get('bestbuy', 'No Data')}
    
    Return JSON ONLY:
    {{
        "best_price": float (0.0 if none found),
        "store": "Amazon/Newegg/BestBuy",
        "description": "Brief description of the item found"
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="kimi-k2.5",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            extra_body={"thinking": {"type": "disabled"}}
        )
        content = response.choices[0].message.content
        if "```json" in content: content = content.split("```json")[1].split("```")[0]
        return json.loads(content)
    except Exception as e:
        print(f"    [!] AI Error: {e}")
        return None

def analyze_used_market(gpu_model, ebay_text):
    if not ebay_text: return None

    prompt = f"""
    I have text from eBay search results for USED "{gpu_model}".
    
    Task:
    1. Identify valid USED GPU listings.
    2. FILTER OUT: "Parts only", "Broken", "Box only", "Cooler", "Read Description".
    3. FILTER OUT: Outliers (prices < $50 or > 200% of average).
    4. Calculate the average price of the valid listings found in the text.
    
    Raw Text:
    {ebay_text}
    
    Return JSON ONLY:
    {{
        "average_price": float (0.0 if none found),
        "listing_count": int (how many valid items used for math)
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="kimi-k2.5",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            extra_body={"thinking": {"type": "disabled"}}
        )
        content = response.choices[0].message.content
        if "```json" in content: content = content.split("```json")[1].split("```")[0]
        return json.loads(content)
    except Exception as e:
        print(f"    [!] AI Error: {e}")
        return None

# --- MAIN LOOP ---
def main():
    migrate_schema()
    driver = setup_driver()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Fetch ALL GPUs
    cursor.execute("SELECT name FROM gpus")
    all_gpus = [r[0] for r in cursor.fetchall()]
    
    # --- RESUME LOGIC ---
    # Python lists start at 0. So GPU #103 is at index 102.
    start_index = 102 
    gpus_to_process = all_gpus[start_index:]
    
    print(f"Found {len(all_gpus)} total GPUs.")
    print(f"RESUMING scan from GPU #{start_index + 1} ({gpus_to_process[0]}).")
    print(f"Skipping first {start_index} GPUs. {len(gpus_to_process)} remaining...")
    # --------------------

    try:
        for i, model in enumerate(gpus_to_process):
            # Calculate real index for logging
            real_index = start_index + i + 1
            print(f"\n[{real_index}/{len(all_gpus)}] Scanning: {model}")
            
            # --- PHASE 1: NEW PRICES ---
            q = model.replace(" ", "+")
            
            text_data = {
                "amazon": get_page_text(driver, f"https://www.amazon.com/s?k={q}+graphics+card"),
                "newegg": get_page_text(driver, f"https://www.newegg.com/p/pl?d={q}&N=4814"), # N=4814 is New Condition
                "bestbuy": get_page_text(driver, f"https://www.bestbuy.com/site/searchpage.jsp?st={q}+gpu")
            }
            
            new_result = analyze_new_market(model, text_data)
            
            if new_result and new_result.get('best_price', 0) > 0:
                price = new_result['best_price']
                print(f"  -> Best New: ${price} @ {new_result['store']}")
                cursor.execute("UPDATE gpus SET new_avg = ? WHERE name = ?", (price, model))
            else:
                print("  -> No valid new prices found.")

            # --- PHASE 2: USED PRICES (eBay) ---
            ebay_url = f"https://www.ebay.com/sch/i.html?_nkw={q}&_sacat=0&LH_ItemCondition=3000&LH_BIN=1"
            ebay_text = get_page_text(driver, ebay_url)
            
            used_result = analyze_used_market(model, ebay_text)
            
            if used_result and used_result.get('average_price', 0) > 0:
                price = used_result['average_price']
                print(f"  -> Avg Used: ${price:.2f} (n={used_result['listing_count']})")
                cursor.execute("UPDATE gpus SET ebay_used_avg = ? WHERE name = ?", (price, model))
            else:
                print("  -> No valid used prices found.")
            
            conn.commit()
            
            # Sleep to protect Selenium driver from being flagged
            time.sleep(random.uniform(5, 8))
            
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        driver.quit()
        conn.close()
        print("Driver closed. Database updated.")

if __name__ == "__main__":
    main()