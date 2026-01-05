# LOC_Scraper

A small, focused command-line tool to iterate Library of Congress (LoC) collection JSON pages, save each item as JSON, and optionally download associated images.

---

## Features ✅

- Paginate LoC collection JSON using the LoC query parameters (sp, c, fo=json)
- Save each item as `item.json` under `output/<item-id-or-title>/`
- Discover and download image files referenced in items
- Skip unchanged files (to avoid re-downloading)
- Configurable page size, start page, polite delay, and toggles to skip JSON or images

## What's New (2026-01-04) ✨

- **`--collection` convenience option**: pass a collection short-name (e.g. `bain`, `brady-handy`) and the `--base-url` and `--output-dir` will be derived automatically when those flags are omitted (e.g., `--collection bain` => base URL `https://www.loc.gov/collections/bain/` and output dir `bain`). (PR: https://github.com/paulseelman/LOC_Scraper/pull/6)

- **Self-check re-run on exhausted page fetch retries**: if a fetch for the next page fails after exhausting retries (default 4), the scraper will schedule a one-time background self-check run — it finishes current work and spawns a subprocess that re-invokes the script with a hidden `--self-check-run` flag so the child won't re-spawn further. This helps detect and verify transient network issues. (PR: https://github.com/paulseelman/LOC_Scraper/pull/7)

- **Per-item image-set stats and cumulative session reporting**: after each item where one or more images were downloaded, the scraper emits a concise info line showing the cumulative number of image sets downloaded and the cumulative bytes downloaded in the current run (human-friendly units). This helps monitor progress and bandwidth usage during long runs. (PR: https://github.com/paulseelman/LOC_Scraper/pull/11)

---

## Requirements 🔧

- Python 3.8+
- The `requests` library

Install the dependency with:

```bash
python -m pip install requests
```

---

## Installation

Clone the repository or copy `LOC_Scraper.py` into your working directory. No build step required.

---

## Usage — Quick Start 💡

Run the script directly with Python (the default behavior uses the `--collection` option):

```bash
# Running with no args will use the default collection 'bain'
python LOC_Scraper.py

# Or explicitly (and tune page size / delay)
python LOC_Scraper.py --collection brady-handy --count 50 --polite-delay 5.0
```

Quick example using the `--collection` convenience option explicitly:

```bash
# Use the 'brady-handy' collection and only download metadata (no images)
python LOC_Scraper.py --collection brady-handy --no-download-images --polite-delay 5.0 --count 50
```

Common options:

- `--collection` : Collection short name **(default: `bain`)**. This is the primary option: when provided (or when omitted, since it defaults to `bain`) it determines the collection to scrape. If `--base-url` or `--output-dir` are not provided, they will be derived from the collection name as follows:
  - base URL: `https://www.loc.gov/collections/<collection>/`
  - output directory: `<collection>`
  Explicit `--base-url` and `--output-dir` always override the derived values.

- `--base-url` : Base LoC collection URL. If omitted, and `--collection` is used (or the default), the script constructs the URL from the collection name as shown above.

- `--output-dir` : Directory to save items and images. If omitted and `--collection` is set (or the default), the script will use the collection name as the output directory.

- `--count` : Items per page (c) (default: 25)
- `--start` : Starting page (sp) (default: 1)
- `--polite-delay` : Delay between pages (seconds) (default: 5.0)
- `--no-download-images` : Do not download images
- `--no-save-json` : Do not save item JSON files
- `--no-skip-existing` : Always overwrite / re-download existing files
- `--log-level` : Logging level (DEBUG, INFO, WARNING, ERROR) (default: INFO)

Note: Internally, when the scraper fails to fetch the next page after exhausting retries, it schedules a one-time background self-check run. This spawns a subprocess that re-invokes the script with an internal (hidden) `--self-check-run` flag; the child run will not spawn further self-checks. You do not normally need to pass `--self-check-run` manually.

Example: download only metadata (no images) with faster pages

```bash
python LOC_Scraper.py --base-url "https://www.loc.gov/collections/bain/" --no-download-images --polite-delay 5.0 --count 50
```

---

## Output structure

By default the scraper writes to `./output/<collection>/` (default collection: `bain`). For each discovered item it creates a folder named after the item's `id`, `url`, or `title` (sanitized) or `item_<n>` as fallback.

Inside each item folder:

- `item.json` — saved JSON representation of the item (unless `--no-save-json`)
- image files — any downloaded images discovered in the item

Files are skipped when unchanged (size, last-modified, or content hash checks are used) unless `--no-skip-existing` is set.

## Sample JSON files (for development & testing)

This repository includes two sample JSON files at the project root to make it easy to write tests or experiment manually:

- `sample_item.json` — a representative single item JSON (useful for unit-testing `_find_image_urls`, `_sanitize_name`, and `_save_item_and_images`).
- `sample_page.json` — a small example of a LoC collection page (useful for exercising `paginate_and_iterate_child_loc`).

Quick examples:

- Inspect discovered images from `sample_item.json`:

```bash
python - <<'PY'
import json
from LOC_Scraper import _find_image_urls
print(_find_image_urls(json.load(open('sample_item.json'))))
PY
```

- Use `sample_page.json` in tests by loading it and passing its `results` to your test helpers.

Include these files when adding or updating unit tests so other contributors and AI agents can run examples offline.

---

## Notes & Tips ⚠️

- Use `--polite-delay` to avoid overloading the LoC servers (the default is 5s).
- The tool preserves existing query parameters on `--base-url` and merges required parameters (fo=json, c, sp).
- **Self-check on exhausted retries:** when a fetch for the *next* page fails after exhausting retries (default 4), the scraper will schedule a one-time self-check run: it finishes current work and spawns a background subprocess that re-invokes the script with a hidden `--self-check-run` flag. The child run will not spawn further self-checks, preventing recursion. This helps verify whether intermittent network issues prevented page retrieval.
- **Collection short-name convenience:** you can now pass `--collection <name>` (e.g. `bain`, `brady-handy`, `abdul-hamid-ii`) and the `--base-url` and `--output-dir` will be derived from it when those flags are not explicitly provided. Example: `--collection bain` results in base URL `https://www.loc.gov/collections/bain/` and output directory `bain`.
- The built-in image detection is heuristic; if images are nested under uncommon keys you may need to adjust the code.
- After each item's image set is saved (when at least one image was downloaded for that item), the scraper prints a concise info line showing the **cumulative number of image sets** downloaded and the **cumulative bytes** downloaded in the current run (human-friendly units).
- Output now uses Python's `logging`; set `--log-level` (default `INFO`) to control verbosity when running the tool.

---

## Development & Contributing 🔧

Contributions are welcome. Open an issue or submit a PR with improvements, bug fixes, or tests.

---

## License

This project is licensed under the Apache License 2.0 — see the `LICENSE` file for details.
