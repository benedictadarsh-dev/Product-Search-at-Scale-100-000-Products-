import http.server
import json
import urllib.parse
import urllib.request
import sqlite3
import time
import os

PORT = 3002
DB_FILE = os.path.join(os.path.dirname(__file__), "products_100k.db")
MEILI_URL = "http://127.0.0.1:7700"
STATIC_DIR = os.path.join(os.path.dirname(__file__), "public")

class SearchHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query_params = urllib.parse.parse_qs(parsed.query)

        if path == "/api/search/sql":
            self.handle_sql_search(query_params)
        elif path == "/api/search/meili":
            self.handle_meili_search(query_params)
        elif path == "/api/benchmarks":
            self.handle_benchmarks()
        elif path == "/" or path == "/index.html":
            self.serve_index()
        else:
            super().do_GET()

    def serve_index(self):
        index_file = os.path.join(STATIC_DIR, "index.html")
        if os.path.exists(index_file):
            with open(index_file, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404, "Index file not found")

    def handle_sql_search(self, params):
        q = params.get("q", [""])[0].strip()
        cat = params.get("category", [None])[0]
        max_p = params.get("max_price", [None])[0]

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        conditions = []
        sql_params = []

        if q:
            pattern = f"%{q}%"
            conditions.append("(title LIKE ? OR description LIKE ? OR tags LIKE ?)")
            sql_params.extend([pattern, pattern, pattern])

        if cat and cat != "all":
            conditions.append("category = ?")
            sql_params.append(cat)

        if max_p:
            conditions.append("price <= ?")
            sql_params.append(float(max_p))

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT id, title, brand, category, price, rating, in_stock, description FROM products{where_clause} LIMIT 25"

        t0 = time.perf_counter()
        cursor.execute(sql, sql_params)
        rows = cursor.fetchall()
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        count_sql = f"SELECT COUNT(*) FROM products{where_clause}"
        cursor.execute(count_sql, sql_params)
        total_hits = cursor.fetchone()[0]
        conn.close()

        results = [
            {
                "id": r[0],
                "title": r[1],
                "brand": r[2],
                "category": r[3],
                "price": r[4],
                "rating": r[5],
                "in_stock": bool(r[6]),
                "description": r[7]
            }
            for r in rows
        ]

        payload = {
            "engine": "SQL LIKE (SQLite 100k full table scan)",
            "queryTimeMs": round(elapsed_ms, 2),
            "totalHits": total_hits,
            "returnedCount": len(results),
            "results": results
        }
        self.send_json(payload)

    def handle_meili_search(self, params):
        q = params.get("q", [""])[0].strip()
        cat = params.get("category", [None])[0]
        max_p = params.get("max_price", [None])[0]

        filters = []
        if cat and cat != "all":
            filters.append(f"category = '{cat}'")
        if max_p:
            filters.append(f"price <= {float(max_p)}")

        body = {
            "q": q,
            "limit": 25
        }
        if filters:
            body["filter"] = " AND ".join(filters)

        t0 = time.perf_counter()
        req = urllib.request.Request(
            f"{MEILI_URL}/indexes/products/search",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            results = [
                {
                    "id": h["id"],
                    "title": h["title"],
                    "brand": h["brand"],
                    "category": h["category"],
                    "price": h["price"],
                    "rating": h["rating"],
                    "in_stock": h["in_stock"],
                    "description": h["description"]
                }
                for h in data.get("hits", [])
            ]

            payload = {
                "engine": "Meilisearch v1.54.3 (Typo-Tolerant Engine)",
                "queryTimeMs": round(elapsed_ms, 2),
                "internalProcessingMs": data.get("processingTimeMs", 0),
                "totalHits": data.get("estimatedTotalHits", len(results)),
                "returnedCount": len(results),
                "results": results
            }
        except Exception as e:
            payload = {
                "error": str(e),
                "queryTimeMs": 0,
                "totalHits": 0,
                "results": []
            }

        self.send_json(payload)

    def handle_benchmarks(self):
        bench_file = os.path.join(os.path.dirname(__file__), "benchmark_results.json")
        if os.path.exists(bench_file):
            with open(bench_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.send_json(data)
        else:
            self.send_json({"status": "benchmarks_pending"})

    def send_json(self, data):
        content = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(content)

def run():
    os.makedirs(STATIC_DIR, exist_ok=True)
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), SearchHandler)
    print(f"[SearchService] Running side-by-side search dashboard on http://localhost:{PORT}")
    server.serve_forever()

if __name__ == "__main__":
    run()
