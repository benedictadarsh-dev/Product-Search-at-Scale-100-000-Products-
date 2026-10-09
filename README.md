# Product Search at Scale

A side-by-side search experiment that compares SQLite `LIKE` queries with Meilisearch on a generated catalogue of 100,000 products. It shows why an inverted index is a stronger fit for typo-tolerant, filtered product search than a relational substring scan.

The project includes a browser dashboard, a deterministic dataset generator, a Python HTTP service, and a benchmark suite that measures latency and result quality for both engines.

## What this demonstrates

- Generating a reproducible 100,000-product SQLite dataset
- SQL `LIKE` search across title, description, and tags
- Meilisearch indexing, filters, ranking, and typo tolerance
- Side-by-side search results in a local dashboard
- Benchmarking mean, p50, p95, and p99 latency across realistic queries
- Comparing result recall for multi-word and misspelled searches

## Prerequisites

- Python 3.10 or later
- Meilisearch running locally at `http://127.0.0.1:7700`

The Python scripts use the standard library, so no Python packages need to be installed.

## Getting started

Start Meilisearch in one terminal. If you download the Windows binary, run it from the project folder:

```powershell
.\meilisearch.exe
```

In a second terminal, create the SQLite dataset and populate the Meilisearch index:

```bash
python generate_dataset.py --index-meili
```

Start the dashboard service:

```bash
python search_service.py
```

Open `http://localhost:3002` to compare searches.

## Run benchmarks

With Meilisearch running and the index populated:

```bash
python benchmark_comparison.py
```

The benchmark writes `benchmark_results.json`, which the dashboard can serve at `GET /api/benchmarks`.

## API endpoints

| Endpoint | Description |
| --- | --- |
| `GET /api/search/sql?q=...` | Searches SQLite using `LIKE` |
| `GET /api/search/meili?q=...` | Searches Meilisearch with typo tolerance |
| `GET /api/benchmarks` | Returns saved benchmark results when available |

Both search endpoints accept optional `category` and `max_price` query parameters.

## Project structure

```text
generate_dataset.py       Creates the product catalogue and optionally indexes Meilisearch
benchmark_comparison.py   Runs the SQL and Meilisearch comparison suite
search_service.py         Serves the dashboard and search APIs on port 3002
public/index.html         Browser dashboard
```

## Notes

The generated SQLite database, Meilisearch data, downloaded search binary, and benchmark output are intentionally ignored by Git. This keeps the repository lightweight and lets each user generate the same dataset locally.

