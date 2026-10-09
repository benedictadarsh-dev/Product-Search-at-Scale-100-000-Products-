import sqlite3
import urllib.request
import urllib.parse
import json
import time
import os
import statistics

DB_FILE = os.path.join(os.path.dirname(__file__), "products_100k.db")
MEILI_URL = "http://127.0.0.1:7700"

BENCHMARK_CASES = [
    {
        "id": "Q1_EXACT_KEYWORD",
        "name": "Single Word Keyword",
        "query": "Ultra",
        "category": None,
        "max_price": None,
        "desc": "Common single keyword across title and description"
    },
    {
        "id": "Q2_HIGH_FREQUENCY",
        "name": "High-Frequency Keyword",
        "query": "Wireless",
        "category": None,
        "max_price": None,
        "desc": "Ubiquitous keyword appearing across thousands of items"
    },
    {
        "id": "Q3_CATEGORY_FILTER",
        "name": "Keyword + Category Filter",
        "query": "Pro",
        "category": "Laptops",
        "max_price": None,
        "desc": "Keyword constrained to specific category"
    },
    {
        "id": "Q4_MULTI_FILTER",
        "name": "Keyword + Category + Max Price",
        "query": "Gaming",
        "category": "Keyboards",
        "max_price": 150.0,
        "desc": "Complex query combining text search with categorical & range filters"
    },
    {
        "id": "Q5_MULTI_WORD_ORDERED",
        "name": "Multi-Word (In-Order)",
        "query": "Mechanical Gaming Keyboard",
        "category": None,
        "max_price": None,
        "desc": "Multiple tokens in consecutive order"
    },
    {
        "id": "Q6_MULTI_WORD_UNORDERED",
        "name": "Multi-Word (Out-of-Order)",
        "query": "Keyboard Mechanical Gaming",
        "category": None,
        "max_price": None,
        "desc": "Multiple tokens with shuffled word order"
    },
    {
        "id": "Q7_PREFIX_AUTOCOMPLETE",
        "name": "Prefix Auto-complete",
        "query": "smartw",
        "category": None,
        "max_price": None,
        "desc": "Partial token typed while searching"
    },
    {
        "id": "Q8_TYPO_1_CHAR",
        "name": "1-Character Typo (Phonetic)",
        "query": "headfone",
        "category": None,
        "max_price": None,
        "desc": "Common misspelling of 'headphone'"
    },
    {
        "id": "Q9_TYPO_BRAND",
        "name": "1-Character Typo (Brand Name)",
        "query": "Samusng",
        "category": None,
        "max_price": None,
        "desc": "Common transposition of 'Samsung'"
    },
    {
        "id": "Q10_TYPO_2_CHAR",
        "name": "2-Character Severe Typo",
        "query": "earbds",
        "category": None,
        "max_price": None,
        "desc": "Severe omission typo of 'earbuds'"
    }
]

def search_sqlite_like(conn, query, category=None, max_price=None, limit=20):
    cursor = conn.cursor()
    # SQL LIKE query pattern matching title or description
    conditions = ["(title LIKE ? OR description LIKE ? OR tags LIKE ?)"]
    pattern = f"%{query}%"
    params = [pattern, pattern, pattern]

    if category:
        conditions.append("category = ?")
        params.append(category)

    if max_price is not None:
        conditions.append("price <= ?")
        params.append(float(max_price))

    where_clause = " AND ".join(conditions)
    sql = f"SELECT id, title, brand, category, price, rating FROM products WHERE {where_clause} LIMIT {limit}"
    
    t0 = time.perf_counter()
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    # Also count total hits for recall measurement
    count_sql = f"SELECT COUNT(*) FROM products WHERE {where_clause}"
    cursor.execute(count_sql, params)
    total_hits = cursor.fetchone()[0]

    return {
        "time_ms": elapsed_ms,
        "total_hits": total_hits,
        "results": rows[:limit]
    }

def search_meilisearch(query, category=None, max_price=None, limit=20):
    filters = []
    if category:
        filters.append(f"category = '{category}'")
    if max_price is not None:
        filters.append(f"price <= {float(max_price)}")

    payload = {
        "q": query,
        "limit": limit
    }
    if filters:
        payload["filter"] = " AND ".join(filters)

    req = urllib.request.Request(
        f"{MEILI_URL}/indexes/products/search",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    t0 = time.perf_counter()
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    return {
        "time_ms": elapsed_ms,
        "total_hits": data.get("estimatedTotalHits", len(data.get("hits", []))),
        "results": [(h["id"], h["title"], h["brand"], h["category"], h["price"], h["rating"]) for h in data.get("hits", [])]
    }

def percentile(data, p):
    data_sorted = sorted(data)
    idx = int(len(data_sorted) * (p / 100.0))
    return data_sorted[min(idx, len(data_sorted) - 1)]

def run_benchmarks(iterations=15):
    print("================================================================================")
    print("PROJECT 46: SQL LIKE vs MEILISEARCH PERFORMANCE & QUALITY EVALUATION")
    print(f"Corpus: 100,000 Products | Iterations per query: {iterations}")
    print("================================================================================\n")

    conn = sqlite3.connect(DB_FILE)
    overall_results = []

    for case in BENCHMARK_CASES:
        print(f"--> Running Scenario: [{case['name']}] (Query: \"{case['query']}\")")
        
        # 1. Warm-up runs
        search_sqlite_like(conn, case["query"], case["category"], case["max_price"])
        search_meilisearch(case["query"], case["category"], case["max_price"])

        # 2. Benchmark SQL LIKE
        sql_times = []
        sql_data = None
        for _ in range(iterations):
            res = search_sqlite_like(conn, case["query"], case["category"], case["max_price"])
            sql_times.append(res["time_ms"])
            sql_data = res

        # 3. Benchmark Meilisearch
        meili_times = []
        meili_data = None
        for _ in range(iterations):
            res = search_meilisearch(case["query"], case["category"], case["max_price"])
            meili_times.append(res["time_ms"])
            meili_data = res

        sql_mean = statistics.mean(sql_times)
        sql_p50 = percentile(sql_times, 50)
        sql_p95 = percentile(sql_times, 95)
        sql_p99 = percentile(sql_times, 99)

        meili_mean = statistics.mean(meili_times)
        meili_p50 = percentile(meili_times, 50)
        meili_p95 = percentile(meili_times, 95)
        meili_p99 = percentile(meili_times, 99)

        speedup = sql_mean / max(meili_mean, 0.001)

        result_row = {
            "id": case["id"],
            "name": case["name"],
            "query": case["query"],
            "category": case["category"],
            "max_price": case["max_price"],
            "sql": {
                "mean_ms": round(sql_mean, 2),
                "p50_ms": round(sql_p50, 2),
                "p95_ms": round(sql_p95, 2),
                "p99_ms": round(sql_p99, 2),
                "total_hits": sql_data["total_hits"],
                "sample_titles": [r[1] for r in sql_data["results"][:2]]
            },
            "meilisearch": {
                "mean_ms": round(meili_mean, 2),
                "p50_ms": round(meili_p50, 2),
                "p95_ms": round(meili_p95, 2),
                "p99_ms": round(meili_p99, 2),
                "total_hits": meili_data["total_hits"],
                "sample_titles": [r[1] for r in meili_data["results"][:2]]
            },
            "speedup": round(speedup, 1),
            "quality_verdict": "SQL LIKE Failed" if (sql_data["total_hits"] == 0 and meili_data["total_hits"] > 0) else "Both Returned Matches"
        }
        overall_results.append(result_row)

        print(f"    SQL LIKE:    Mean={sql_mean:.2f}ms | p95={sql_p95:.2f}ms | Hits={sql_data['total_hits']}")
        print(f"    Meilisearch: Mean={meili_mean:.2f}ms | p95={meili_p95:.2f}ms | Hits={meili_data['total_hits']}")
        print(f"    Speedup:     {speedup:.1f}x faster with Meilisearch")
        print(f"    Quality:     {result_row['quality_verdict']}\n")

    conn.close()

    # Save detailed JSON summary
    summary_path = os.path.join(os.path.dirname(__file__), "benchmark_results.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(overall_results, f, indent=2)

    print(f"Benchmark completed successfully! Detailed data saved to {summary_path}")
    return overall_results

if __name__ == "__main__":
    run_benchmarks()
