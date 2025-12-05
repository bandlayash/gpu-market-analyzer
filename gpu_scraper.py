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
        "release_date": None,
        "memory_amount": None,
        "memory_type": None,
        "memory_bus": None,
        "chip": None,
        "bus": None,
        "gpu_clock": None,
        "memory_clock": None,
        "cores": None,
        "tmus": None,
        "rops": None
    }

    name_tag = block.select_one("a.item-name")
    gpu["name"] = name_tag.get_text(strip = True)

    rows = block.select(".item-properties-row")

    if len(rows) > 0:
            spans = rows[0].select("span")
            gpu["release_date"] = spans[0].get_text(strip=True)
            mem_info = spans[1].get_text(strip=True)
            mem_parts = [p.strip() for p in mem_info.split("/")]
            if len(mem_parts) == 3:
                gpu["memory_amount"] = mem_parts[0]
                gpu["memory_type"] = mem_parts[1]
                gpu["memory_bus"] = mem_parts[2]

    if len(rows) > 1:
            spans = rows[1].select("span")
            chip = spans[0].get_text(strip=True)
            gpu["chip"] = chip
            gpu["bus"] = spans[1].get_text(strip=True)
            clocks = spans[2].get_text(strip=True)
            clock_parts = [p.strip() for p in clocks.split("/")]
            if len(clock_parts) == 2:
                gpu["gpu_clock"] = clock_parts[0]
                gpu["memory_clock"] = clock_parts[1]

    if len(rows) > 2:
            row3 = rows[2].get_text(strip=True)
            stats = [p.strip() for p in row3.split("/")]
            if len(stats) == 3:
                gpu["cores"] = stats[0]
                gpu["tmus"] = stats[1]
                gpu["rops"] = stats[2]

    items.append(gpu)

#---------------------------------DATABASE---------------------------------------

conn = sqlite3.connect("gpus.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS gpus (
    name TEXT PRIMARY KEY,
    release_date TEXT,
    memory_amount TEXT,
    memory_type TEXT,
    memory_bus TEXT,
    chip TEXT,
    bus TEXT,
    gpu_clock TEXT,
    memory_clock TEXT,
    cores TEXT,
    tmus TEXT,
    rops TEXT
)
""")

for item in items:
    cur.execute("""
        INSERT INTO gpus VALUES (
            :name, :release_date, :memory_amount, :memory_type, :memory_bus,
            :chip, :bus, :gpu_clock, :memory_clock, :cores, :tmus, :rops
        )
    """, item)

conn.commit()
conn.close()