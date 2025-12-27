# GitHub Copilot / AI Agent Instructions for LOC_Scraper ✅

Purpose: Help an AI coding agent be productive quickly by summarizing the project's architecture, conventions, workflows, and key places to change behavior safely.

## Quick summary
- Single-file CLI Python tool: `LOC_Scraper.py` (entrypoint: `main()`).
- Iterates Library of Congress collection JSON pages (LoC uses `?fo=json&c=<count>&sp=<page>`), saves each item as JSON, and optionally downloads images into `output/`.
- Minimal deps: Python 3.8+, `requests`.

## Key files
- `LOC_Scraper.py` — all application logic. Important functions:
  - `paginate_and_iterate_child_loc(...)` — main pagination & orchestration loop
  - `fetch_json_page(...)` — builds URL and fetches JSON pages (handles retries)
  - `get_child_list(...)` — extracts child list (default key: `results`)
  - `_save_item_and_images(...)` — writes `item.json` and downloads images with skip logic
  - `_find_image_urls(...)`, `_image_head_info(...)`, `_compute_file_hash(...)`, `_sanitize_name(...)` — helper utilities
- `README.md` — user-facing usage and examples
- `LICENSE` — Apache 2.0
- `output/`, `test_output/`, `tmp_test_output/` — sample output locations (not tests)

## Project-specific conventions & patterns 🔧
- CLI-first, single-script design: changes should preserve a simple CLI usage model.
- Output now uses Python's `logging`; diagnostic messages use `logging` and are controllable via the `--log-level` CLI flag (default: `INFO`).
- Network operations use a single `requests.Session()` for efficiency and are resilient:
  - `fetch_json_page()` retries up to `max_retries` with exponential backoff.
  - Image HEAD uses a fallback GET (Range 0-0) when HEAD returns 405.
- File skipping behavior is deliberate and multi-step:
  - Prefer `Content-Length` and `Last-Modified` headers; fallback to hashing when necessary.
  - `--no-skip-existing` forces overwrite/re-download.
- URL handling preserves existing query params via `build_url_with_params()` — avoid stripping params when making changes.

## Typical developer workflows & helpful commands ⚙️
- Install dependency: `python -m pip install requests`
- Run quick scrape: `python LOC_Scraper.py --base-url "https://www.loc.gov/collections/bain/" --output-dir ./output`
- Force re-downloads for debugging: add `--no-skip-existing` and `--no-download-images` as needed.
- Speed up/debug runs: lower `--polite-delay` and `--count` (but be considerate of LoC servers).

## Testing & changing network behavior (practical guidance) ✅
- A minimal pytest-based test suite has been added in `tests/` covering `_find_image_urls`, `_sanitize_name`, `_compute_file_hash`, and `_image_head_info` (HEAD fallback). Run it with:
  1. `python -m pip install -r requirements.txt`
  2. `python -m pytest`

- When adding more tests, mock external HTTP calls:
  - Prefer `responses` or `requests-mock` to simulate LoC endpoints and image servers.
  - Unit-test helpers: `_find_image_urls`, `_sanitize_name`, `_compute_file_hash`, and HEAD fallback in `_image_head_info`.
  - Integration tests should use mocked `requests.Session` so they run offline and deterministically.

## Safe modification notes / gotchas ⚠️
- Be careful when changing default delays, counts, or retry semantics — these control load on LoC servers.
- The image detection is heuristic — if you add image extraction changes, include test vectors for nested/unknown keys.
- Preserving query params during URL build is important; use `build_url_with_params()` where possible.
- Changing output structure: many downstream consumers may rely on `output/<item-id>/item.json` and the naming heuristics — document any breaking changes clearly.

## Example tasks an AI agent can do right away ✅
- Add unit tests for `_find_image_urls` and `_sanitize_name`.
- Add `requirements.txt` with `requests` pinned (use versions compatible with Python 3.8+).
- Add a small `tests/` directory with mocked network tests for `fetch_json_page` and `_image_head_info`.
- Prints have been converted to `logging`. Use `--log-level` to control verbosity; update tests to capture logs when asserting on messages.

## CI / GitHub Actions ✅
- A simple GitHub Actions workflow (`.github/workflows/python-tests.yml`) runs `pytest` on pushes and pull requests to `main`/`master` using Python 3.8-3.10.
- The job installs `requirements.txt` if present, otherwise falls back to installing `requests`, `pytest`, and `responses`.

---
If any areas are unclear or you'd like more examples (test snippets, suggested `requirements.txt`, or a starter test file), tell me which piece to add or iterate on. 🔁
