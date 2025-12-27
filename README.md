# LOC_Scraper

A small, focused command-line tool to iterate Library of Congress (LoC) collection JSON pages, save each item as JSON, and optionally download associated images.

---

## Features ✅

- Paginate LoC collection JSON using the LoC query parameters (sp, c, fo=json)
- Save each item as `item.json` under `output/<item-id-or-title>/`
- Discover and download image files referenced in items
- Skip unchanged files (to avoid re-downloading)
- Configurable page size, start page, polite delay, and toggles to skip JSON or images

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

Run the script directly with Python:

```bash
python LOC_Scraper.py --base-url "https://www.loc.gov/collections/bain/" --output-dir ./output
```

Common options:

- `--base-url` : Base LoC collection URL (default: `https://www.loc.gov/collections/bain/`)
- `--output-dir` : Directory to save items and images (default: `output`)
- `--count` : Items per page (c) (default: 25)
- `--start` : Starting page (sp) (default: 1)
- `--polite-delay` : Delay between items in seconds (default: 5.0)
- `--no-download-images` : Do not download images
- `--no-save-json` : Do not save item JSON files
- `--no-skip-existing` : Always overwrite / re-download existing files

Example: download only metadata (no images) with faster pages

```bash
python LOC_Scraper.py --base-url "https://www.loc.gov/collections/bain/" --no-download-images --polite-delay 1.0 --count 50
```

---

## Output structure

By default the scraper writes to `./output/`. For each discovered item it creates a folder named after the item's `id`, `url`, or `title` (sanitized) or `item_<n>` as fallback.

Inside each item folder:

- `item.json` — saved JSON representation of the item (unless `--no-save-json`)
- image files — any downloaded images discovered in the item

Files are skipped when unchanged (size, last-modified, or content hash checks are used) unless `--no-skip-existing` is set.

---

## Notes & Tips ⚠️

- Use `--polite-delay` to avoid overloading the LoC servers (the default is 5s).
- The tool preserves existing query parameters on `--base-url` and merges required parameters (fo=json, c, sp).
- The built-in image detection is heuristic; if images are nested under uncommon keys you may need to adjust the code.

---

## Development & Contributing 🔧

Contributions are welcome. Open an issue or submit a PR with improvements, bug fixes, or tests.

---

## License

This project is licensed under the Apache License 2.0 — see the `LICENSE` file for details.

---

If you'd like, I can also add a short examples directory with sample outputs or add a minimal `requirements.txt`. Would you like that? 🚀
