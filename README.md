# Product Search at Scale

Comparison of SQLite `LIKE` search and typo-tolerant Meilisearch over a generated 100,000-product catalogue.

## Run

```bash
python generate_dataset.py
python search_service.py
```

Run `python benchmark_comparison.py` after starting Meilisearch locally.

