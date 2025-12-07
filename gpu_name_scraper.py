from bs4 import BeautifulSoup
import requests
import sqlite3


#---------------------------------SCRAPING---------------------------------------

base_url = "https://www.techpowerup.com/gpu-specs/"
response = requests.get(base_url)
soup = BeautifulSoup(response.text, 'html.parser')

items = []

for block in soup.select("div.items-mobile--item"):
    gpu = {
        "name": None,
    }

    name_tag = block.select_one("a.item-name")
    gpu["name"] = name_tag.get_text(strip = True)

    rows = block.select(".item-properties-row")

    items.append(gpu)

#---------------------------------DATABASE---------------------------------------

conn = sqlite3.connect("gpus.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS gpus (
    name TEXT PRIMARY KEY,
)
""")

for item in items:
    cur.execute("""
        INSERT INTO gpus VALUES (
            :name
        )
    """, item)

conn.commit()
conn.close()