import sqlite3
import random
import time
import json
import os
import sys
import urllib.request

# Deterministic seed for reproducible evaluation
random.seed(42)

TOTAL_PRODUCTS = 100000
DB_FILE = os.path.join(os.path.dirname(__file__), "products_100k.db")
MEILI_URL = "http://127.0.0.1:7700"

BRANDS = [
    "Apple", "Samsung", "Sony", "Dell", "Logitech", "Bose", "Asus", 
    "Corsair", "Canon", "Razer", "Dyson", "Lenovo", "LG", "Anker", 
    "Microsoft", "HP", "Keychron", "Sennheiser", "Nvidia", "SteelSeries"
]

CATEGORIES = [
    "Smartphones", "Laptops", "Audio", "Monitors", "Keyboards", 
    "Cameras", "Gaming", "Wearables", "Storage", "Accessories"
]

ADJECTIVES = [
    "Ultra", "Pro", "Max", "Wireless", "Ergonomic", "Compact", "Gaming", 
    "Studio", "Mechanical", "Precision", "Portable", "Rugged", "Smart", 
    "Noise-Cancelling", "High-Speed", "RGB", "Silent", "Fast-Charging"
]

NOUNS_BY_CATEGORY = {
    "Smartphones": ["Phone", "Pro Phone", "Ultra Mobile", "Foldable Phone", "5G Device"],
    "Laptops": ["Notebook", "Ultrabook", "Workstation", "Gaming Laptop", "Creator Book"],
    "Audio": ["Headphones", "Earbuds", "Soundbar", "Studio Monitor", "Speaker"],
    "Monitors": ["Curved Display", "Gaming Monitor", "OLED Screen", "4K Ultrawide", "IPS Panel"],
    "Keyboards": ["Mechanical Keyboard", "Custom Keyboard", "Low-Profile Board", "Wireless Keeb"],
    "Cameras": ["Mirrorless Camera", "Cinema Cam", "Vlogging Kit", "Action Cam", "DSLR Body"],
    "Gaming": ["Controller", "Handheld Console", "VR Headset", "Racing Wheel", "Flight Stick"],
    "Wearables": ["Smartwatch", "Fitness Tracker", "Smart Ring", "Health Band"],
    "Storage": ["NVMe SSD", "External Hard Drive", "MicroSD Card", "RAID Enclosure"],
    "Accessories": ["USB-C Hub", "Magnetic Stand", "GaN Charger", "Cable Pack", "Desk Mat"]
}

FEATURES = [
    "Engineered with aerospace-grade materials for exceptional durability.",
    "Features ultra-low latency response times tailored for competitive gaming and demanding pros.",
    "Equipped with next-generation adaptive battery management lasting up to 48 hours.",
    "Includes active noise cancellation with dual MEMS microphone beamforming arrays.",
    "Offers lightning-fast Thunderbolt 4 and USB 3.2 Gen 2 transfer rates.",
    "Factory calibrated color profile covering 100% sRGB and 98% DCI-P3 gamut.",
    "Hot-swappable socket design supporting both 3-pin and 5-pin mechanical switches.",
    "IP68 water and dust resistance certification for rugged outdoor operation."
]

def generate_product(idx):
    category = CATEGORIES[idx % len(CATEGORIES)]
    brand = BRANDS[(idx * 7) % len(BRANDS)]
    noun_list = NOUNS_BY_CATEGORY[category]
    noun = noun_list[(idx * 13) % len(noun_list)]
    adj1 = ADJECTIVES[(idx * 17) % len(ADJECTIVES)]
    adj2 = ADJECTIVES[(idx * 23) % len(ADJECTIVES)]
    
    # Generate realistic titles e.g. "Apple Pro Wireless Ultra Headphones"
    title = f"{brand} {adj1} {noun} {adj2} v{((idx % 9) + 1)}"
    price = round(random.uniform(19.99, 2499.99), 2)
    rating = round(random.uniform(3.0, 5.0), 1)
    in_stock = 1 if (idx % 8 != 0) else 0  # 87.5% in stock
    
    desc_feature1 = FEATURES[(idx * 3) % len(FEATURES)]
    desc_feature2 = FEATURES[(idx * 5) % len(FEATURES)]
    description = f"{brand} {title}. {desc_feature1} {desc_feature2} Ideal for {category.lower()} enthusiasts."
    
    tags = f"{category.lower()}, {brand.lower()}, {adj1.lower()}, {adj2.lower()}, electronics"
    
    return (
        idx,
        title,
        brand,
        category,
        price,
        rating,
        in_stock,
        description,
        tags
    )

def setup_sqlite():
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
        except Exception:
            pass

    print(f"[SQLite] Creating database at: {DB_FILE}")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE products (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        brand TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        rating REAL NOT NULL,
        in_stock INTEGER NOT NULL,
        description TEXT NOT NULL,
        tags TEXT NOT NULL
    );
    """)

    # Standard B-Tree Indexes on filterable columns
    cursor.execute("CREATE INDEX idx_products_category ON products(category);")
    cursor.execute("CREATE INDEX idx_products_price ON products(price);")
    cursor.execute("CREATE INDEX idx_products_stock ON products(in_stock);")
    cursor.execute("CREATE INDEX idx_products_rating ON products(rating);")
    cursor.execute("CREATE INDEX idx_products_title ON products(title);")

    print(f"[SQLite] Generating and inserting {TOTAL_PRODUCTS:,} records...")
    t0 = time.time()
    
    batch = []
    for i in range(1, TOTAL_PRODUCTS + 1):
        batch.append(generate_product(i))
        if len(batch) >= 10000:
            cursor.executemany("""
                INSERT INTO products (id, title, brand, category, price, rating, in_stock, description, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
            batch = []
            print(f"  Inserted {i:,} / {TOTAL_PRODUCTS:,} records...")

    if batch:
        cursor.executemany("""
            INSERT INTO products (id, title, brand, category, price, rating, in_stock, description, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, batch)

    conn.commit()
    conn.close()
    elapsed = time.time() - t0
    print(f"[SQLite] Successfully inserted {TOTAL_PRODUCTS:,} records in {elapsed:.2f} seconds.")

def check_meili_ready():
    req = urllib.request.Request(f"{MEILI_URL}/health")
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False

def configure_and_index_meilisearch():
    if not check_meili_ready():
        print(f"[Meilisearch] Server is not currently running at {MEILI_URL}. Please start meilisearch.exe first.")
        return False

    print(f"[Meilisearch] Configuring index 'products'...")
    # Create or reset index
    req_delete = urllib.request.Request(f"{MEILI_URL}/indexes/products", method="DELETE")
    try:
        urllib.request.urlopen(req_delete, timeout=5)
    except Exception:
        pass
    time.sleep(1)

    req_create = urllib.request.Request(
        f"{MEILI_URL}/indexes",
        data=json.dumps({"uid": "products", "primaryKey": "id"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    urllib.request.urlopen(req_create, timeout=5)
    time.sleep(1)

    # Set Filterable and Searchable Attributes
    settings = {
        "searchableAttributes": ["title", "brand", "description", "tags"],
        "filterableAttributes": ["category", "price", "in_stock", "rating", "brand"],
        "sortableAttributes": ["price", "rating"],
        "typoTolerance": {
            "enabled": True,
            "minWordSizeForTypos": {
                "oneTypo": 4,
                "twoTypos": 8
            }
        }
    }

    req_settings = urllib.request.Request(
        f"{MEILI_URL}/indexes/products/settings",
        data=json.dumps(settings).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="PATCH"
    )
    urllib.request.urlopen(req_settings, timeout=5)
    print("[Meilisearch] Index settings updated.")

    # Read from SQLite and index into Meilisearch in batches of 10,000
    print(f"[Meilisearch] Streaming {TOTAL_PRODUCTS:,} products to Meilisearch...")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, brand, category, price, rating, in_stock, description, tags FROM products")

    batch_size = 10000
    docs = []
    total_sent = 0
    t0 = time.time()

    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
        for r in rows:
            docs.append({
                "id": r[0],
                "title": r[1],
                "brand": r[2],
                "category": r[3],
                "price": r[4],
                "rating": r[5],
                "in_stock": bool(r[6]),
                "description": r[7],
                "tags": r[8]
            })

        req_docs = urllib.request.Request(
            f"{MEILI_URL}/indexes/products/documents",
            data=json.dumps(docs).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req_docs, timeout=30)
        total_sent += len(docs)
        print(f"  Sent {total_sent:,} / {TOTAL_PRODUCTS:,} documents to Meilisearch...")
        docs = []

    conn.close()
    elapsed = time.time() - t0
    print(f"[Meilisearch] Ingestion completed in {elapsed:.2f} seconds. Waiting for tasks to process...")
    return True

if __name__ == "__main__":
    setup_sqlite()
    if "--index-meili" in sys.argv:
        configure_and_index_meilisearch()
