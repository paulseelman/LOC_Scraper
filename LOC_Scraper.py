import json
import time
import os
import re
import argparse
import tempfile
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl
from email.utils import parsedate_to_datetime

import requests
import logging
import subprocess
import sys

logger = logging.getLogger(__name__)

# Session-level image-set statistics (reset at the start of a run)
_session_image_sets = 0
_session_image_bytes = 0

def _reset_image_session_stats() -> None:
    """Reset session counters for image sets/bytes."""
    global _session_image_sets, _session_image_bytes
    _session_image_sets = 0
    _session_image_bytes = 0


def _format_bytes(sz: int) -> str:
    """Human-friendly size formatting (bytes -> KB/MB)"""
    if sz < 1024:
        return f"{sz} B"
    for unit in ("KiB", "MiB", "GiB"):
        sz /= 1024.0
        if sz < 1024.0:
            return f"{sz:.2f} {unit}"
    return f"{sz:.2f} TiB"


def build_url_with_params(base_url: str, params: Dict[str, Any]) -> str:
    """
    Merge params into base_url query string safely (preserves existing params).
    """
    parts = urlparse(base_url)
    existing = dict(parse_qsl(parts.query, keep_blank_values=True))
    existing.update({k: str(v) for k, v in params.items()})
    new_query = urlencode(existing)
    return urlunparse((parts.scheme, parts.netloc, parts.path, parts.params, new_query, parts.fragment))


def fetch_json_page(
    session: requests.Session,
    base_url: str,
    page_sp: int,
    count_c: int,
    extra_params: Optional[Dict[str, Any]] = None,
    timeout_s: int = 20,
    max_retries: int = 4,
) -> Any:
    """
    Fetch one JSON page using LoC scheme:
      - c = count
      - sp = page
      - fo = json
    """
    params: Dict[str, Any] = {
        "fo": "json",
        "c": count_c,
        "sp": page_sp,
    }
    if extra_params:
        params.update(extra_params)

    url = build_url_with_params(base_url, params)

    for attempt in range(max_retries + 1):
        try:
            resp = session.get(url, timeout=timeout_s)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as e:
            if attempt >= max_retries:
                raise RuntimeError(
                    f"Failed to fetch/parse JSON after {max_retries} retries "
                    f"(sp={page_sp}, c={count_c}). Last error: {e}"
                ) from e
            time.sleep(2 ** attempt)


def get_child_list(data: Any, child_key: str) -> List[Any]:
    """
    Extract list at data[child_key]. For LoC, child_key is often 'results'.
    """
    if not isinstance(data, dict):
        raise ValueError(f"Expected top-level JSON object (dict), got {type(data).__name__}")

    node = data.get(child_key, [])
    if node is None:
        return []
    if not isinstance(node, list):
        raise ValueError(f"Expected '{child_key}' to be a list, got {type(node).__name__}")

    return node


def process_item(item: Any) -> None:
    """
    Replace with your real processing logic.
    Example: print a few useful fields commonly present in LoC results.
    """
    if isinstance(item, dict):
        title = item.get("title")
        url = item.get("url")
        logger.info(f"{title} | {url}")
    else:
        logger.info(json.dumps(item, ensure_ascii=False))


def _find_image_urls(obj: Any) -> List[str]:
    """
    Recurse into the item dict/list and return list of discovered image URLs.
    Simple heuristic: strings starting with http and ending with a common image extension.

    Special-case for LoC tile URLs: when we see a `.../service/...r.jpg` URL, also construct
    the corresponding master TIFF `.../master/...u.tif` (higher-resolution master image).
    """
    urls = set()
    image_exts = ('.jpg', '.jpeg', '.png', '.gif', '.tif', '.tiff', '.webp', '.bmp')
    if isinstance(obj, dict):
        for v in obj.values():
            urls.update(_find_image_urls(v))
    elif isinstance(obj, list):
        for v in obj:
            urls.update(_find_image_urls(v))
    elif isinstance(obj, str):
        # preserve original URL (with query) when returning, but use lowercase/no-query for checks
        no_query = obj.split('?', 1)[0]
        lower = no_query.lower()
        if lower.startswith('http') and lower.endswith(image_exts):
            urls.add(obj)

            # Construct LoC master TIFF when encountering service r.jpg/jpeg URLs
            if '/service/' in lower and (lower.endswith('r.jpg') or lower.endswith('r.jpeg')):
                # replace first /service/ with /master/ and replace r.jpg|r.jpeg -> u.tif
                constructed = re.sub(r'/service/', '/master/', no_query, count=1)
                constructed = re.sub(r'r\.jpe?g$', 'u.tif', constructed, flags=re.IGNORECASE)
                urls.add(constructed)
    return list(urls)


def _sanitize_name(name: str, max_len: int = 100) -> str:
    s = re.sub(r'[^A-Za-z0-9._-]+', '_', name or '')
    return s[:max_len].strip('_') or 'item'


def _image_head_info(session: requests.Session, url: str) -> Tuple[Optional[int], Optional[float], Optional[str]]:
    """Return (content_length, last_modified_epoch, content_type) when available via HEAD/GET fallback."""
    try:
        resp = session.head(url, allow_redirects=True, timeout=20)
        if resp.status_code == 405:
            # HEAD not allowed, attempt a short GET with Range 0-0
            resp = session.get(url, stream=True, headers={"Range": "bytes=0-0"}, timeout=20)
    except requests.RequestException:
        return (None, None, None)

    clen = None
    lm = None
    ctype = None
    if 'Content-Length' in resp.headers:
        try:
            clen = int(resp.headers.get('Content-Length'))
        except (TypeError, ValueError):
            clen = None
    if 'Last-Modified' in resp.headers:
        try:
            lm = parsedate_to_datetime(resp.headers.get('Last-Modified')).timestamp()
        except Exception:
            lm = None
    ctype = resp.headers.get('Content-Type')
    return (clen, lm, ctype)


def _compute_file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def _save_item_and_images(session: requests.Session, item: Any, out_dir: str, idx: int, save_json: bool = True, download_images: bool = True, skip_existing: bool = True) -> None:
    base = Path(out_dir)
    # Track bytes downloaded for this item's image set; this is used to update
    # the session-level cumulative counters and to emit a single info line per set.
    set_bytes = 0
    set_saved_files = 0
    # pick a folder name: prefer id or url or title; fallback to numeric index
    folder_key = None
    if isinstance(item, dict):
        for k in ('id', 'url', 'title'):
            if item.get(k):
                folder_key = item.get(k)
                break
    if not folder_key:
        folder_name = f'item_{idx}'
    else:
        folder_name = _sanitize_name(str(folder_key))
    item_dir = base / folder_name
    item_dir.mkdir(parents=True, exist_ok=True)

    # save JSON copy (skip if identical when requested)
    if save_json:
        existing_json_path = item_dir / 'item.json'
        try:
            if existing_json_path.exists() and skip_existing:
                try:
                    existing = json.load(existing_json_path.open('r', encoding='utf-8'))
                    if existing == item:
                        logger.info(f"Skipping JSON for {folder_name} (unchanged)")
                    else:
                        json.dump(item, existing_json_path.open('w', encoding='utf-8'), ensure_ascii=False, indent=2)
                        logger.info(f"Updated JSON for {folder_name}")
                except (ValueError, OSError):
                    # if existing file is unreadable, overwrite
                    json.dump(item, existing_json_path.open('w', encoding='utf-8'), ensure_ascii=False, indent=2)
                    logger.info(f"Wrote JSON for {folder_name} (replaced corrupted file)")
            else:
                with open(existing_json_path, 'w', encoding='utf-8') as fh:
                    json.dump(item, fh, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning(f"Failed to write JSON for {folder_name}: {e}")

    # find image urls
    if download_images:
        urls = _find_image_urls(item)
        if not urls:
            # some LoC responses put images under 'image' or 'images' keys as dicts with 'url'
            # try shallow check for known patterns
            if isinstance(item, dict):
                for k in ('image', 'images', 'online_media', 'online_media_urls'):
                    v = item.get(k)
                    if v:
                        urls.extend(_find_image_urls(v))
        saved = 0
        for url in urls:
            try:
                # Determine HEAD info to help skipping
                clen, lm, ctype = _image_head_info(session, url)

                # derive filename deterministically
                name = os.path.basename(urlparse(url).path) or f'image_{saved + 1}'
                if not Path(name).suffix and ctype:
                    ext_map = {
                        'image/jpeg': '.jpg',
                        'image/jpg': '.jpg',
                        'image/png': '.png',
                        'image/gif': '.gif',
                        'image/tiff': '.tif',
                        'image/webp': '.webp',
                        'image/bmp': '.bmp',
                    }
                    ext = ext_map.get(ctype.split(';', 1)[0].strip().lower())
                    if ext:
                        name = name + ext
                name = _sanitize_name(name)
                dst = item_dir / name

                if dst.exists() and skip_existing:
                    skipped = False
                    try:
                        if clen is not None:
                            if dst.stat().st_size == clen:
                                logger.info(f"Skipping image (exists, same size): {dst}")
                                skipped = True
                        if not skipped and lm is not None:
                            # compare file mtime to last-modified
                            if dst.stat().st_mtime >= lm:
                                logger.info(f"Skipping image (exists, not older): {dst}")
                                skipped = True
                        if not skipped and clen is None and lm is None:
                            # fallback: compare hash by downloading to temp
                            with tempfile.NamedTemporaryFile(delete=False) as tmpf:
                                try:
                                    r = session.get(url, stream=True, timeout=30)
                                    r.raise_for_status()
                                    for chunk in r.iter_content(8192):
                                        if chunk:
                                            tmpf.write(chunk)
                                    tmpf.flush()
                                    tmp_path = Path(tmpf.name)
                                    if _compute_file_hash(tmp_path) == _compute_file_hash(dst):
                                        logger.info(f"Skipping image (exists, identical content): {dst}")
                                        skipped = True
                                    else:
                                        # capture bytes written, move into place (overwrite)
                                        try:
                                            bytes_written = tmp_path.stat().st_size
                                        except Exception:
                                            bytes_written = None
                                        tmp_path.replace(dst)
                                        logger.info(f"Replaced image (content changed): {dst}")
                                        saved += 1
                                        set_saved_files += 1
                                        if bytes_written:
                                            set_bytes += bytes_written
                                finally:
                                    # ensure no leftover if we replaced
                                    if 'tmp_path' in locals() and tmp_path.exists():
                                        try:
                                            tmp_path.unlink()
                                        except Exception:
                                            pass
                    except OSError as e:
                        print(f"Warning checking existing file {dst}: {e}")

                    if skipped:
                        saved += 0
                        continue

                # if not skipped, download and write to file (atomic)
                with tempfile.NamedTemporaryFile(delete=False, dir=str(item_dir)) as tmpf:
                    try:
                        r = session.get(url, stream=True, timeout=30)
                        r.raise_for_status()
                        for chunk in r.iter_content(8192):
                            if chunk:
                                tmpf.write(chunk)
                        tmpf.flush()
                        tmp_path = Path(tmpf.name)
                        # ensure unique destination name if necessary
                        dst_final = dst
                        i = 1
                        while dst_final.exists() and not skip_existing:
                            dst_final = item_dir / f"{dst.stem}_{i}{dst.suffix}"
                            i += 1
                        try:
                            bytes_written = tmp_path.stat().st_size
                        except Exception:
                            bytes_written = None
                        tmp_path.replace(dst_final)
                        logger.info(f"Saved image: {dst_final}")
                        saved += 1
                        set_saved_files += 1
                        if bytes_written:
                            set_bytes += bytes_written
                    finally:
                        # cleanup if something went wrong and tmpf still exists
                        if 'tmp_path' in locals() and tmp_path.exists() and not tmp_path.samefile(dst if dst.exists() else tmp_path):
                            try:
                                tmp_path.unlink()
                            except Exception:
                                pass

            except requests.RequestException as e:
                logger.warning(f"Failed to download {url}: {e}")

        # After processing this item's discovered URLs, if we downloaded any files
        # count this as one image set and update session cumulative counters and log
        # a concise info line for the user.
        if set_saved_files > 0:
            global _session_image_sets, _session_image_bytes
            _session_image_sets += 1
            _session_image_bytes += set_bytes
            logger.info(f"Image sets: {_session_image_sets} | cumulative downloaded: {_format_bytes(_session_image_bytes)}")


def paginate_and_iterate_child_loc(
    base_url: str,
    child_key: str = "results",
    count_c: int = 25,
    start_sp: int = 1,
    extra_params: Optional[Dict[str, Any]] = None,
    stop_on_short_page: bool = True,
    polite_delay_s: float = 0.0,
    output_dir: str = "output",
    save_json: bool = True,
    download_images: bool = True,
    skip_existing: bool = True,
) -> None:
    """
    Paginate LoC collection JSON:
      GET ...?fo=json&c=<count>&sp=<page>

    For each page:
      - iterate data[child_key] (default: 'results')
      - increment sp

    Stops when:
      - results list is empty/missing
      - (optional) results list length < count_c

    Saves a JSON copy of each item and downloads discovered images into
    `output_dir/<item-id-or-title>/` when requested.
    """
    sp = start_sp
    total_processed = 0
    recheck_needed = False

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    with requests.Session() as session:
        while True:
            try:
                data = fetch_json_page(
                    session=session,
                    base_url=base_url,
                    page_sp=sp,
                    count_c=count_c,
                    extra_params=extra_params,
                )
            except RuntimeError as e:
                # If the fetch failed due to exhausting retries while attempting to fetch the next
                # page (e.g., "Failed to fetch/parse JSON after 4 retries ..."), record that we
                # should perform a self-check run later and stop the pagination loop so we can
                # finish cleanly.
                msg = str(e)
                if "Failed to fetch/parse JSON after" in msg:
                    logger.warning(f"Fetch failed for sp={sp}: {e}. Scheduling a self-check run after completion.")
                    recheck_needed = True
                    break
                # otherwise, re-raise unexpected runtime errors
                raise

            items = get_child_list(data, child_key)

            if not items:
                logger.info(f"Stopping: no '{child_key}' items found at sp={sp}. Total processed: {total_processed}")
                break

            for item in items:
                process_item(item)
                # save JSON and images (if requested)
                try:
                    _save_item_and_images(
                        session,
                        item,
                        output_dir,
                        total_processed + 1,
                        save_json=save_json,
                        download_images=download_images,
                        skip_existing=skip_existing,
                    )
                except Exception as e:
                    logger.warning(f"Error saving item {total_processed + 1}: {e}")

                total_processed += 1

            logger.info(f"Processed sp={sp}: {len(items)} items (total {total_processed})")

            if stop_on_short_page and len(items) < count_c:
                logger.info(f"Stopping: sp={sp} returned {len(items)} (< {count_c}). Total processed: {total_processed}")
                break

            sp += 1

            if polite_delay_s > 0:
                time.sleep(polite_delay_s)

    # Return whether a self-check run should be scheduled by the caller
    return recheck_needed


def main():
    parser = argparse.ArgumentParser(description="Iterate LoC collection, save item JSON and images.")
    # Allow deriving base URL and output directory from a short collection name
    parser.add_argument("--collection", default="bain", help="Collection short name (e.g. 'bain' or 'brady-handy'). This is now the primary option and defaults to 'bain' when omitted; --base-url and --output-dir are derived from it unless explicitly set.")
    parser.add_argument("--base-url", default=None, help="Base LoC collection URL; if omitted and --collection is provided it will be constructed from the collection name")
    parser.add_argument("--output-dir", default=None, help="Directory to save items and images; if omitted and --collection is provided it will use the collection name")
    parser.add_argument("--count", type=int, default=25, help="Items per page (c)")
    parser.add_argument("--start", type=int, default=1, help="Starting page (sp)")
    parser.add_argument("--polite-delay", type=float, default=5.0, help="Delay between items (seconds)")
    parser.add_argument("--no-download-images", action="store_true", help="Do not download images")
    parser.add_argument("--no-save-json", action="store_true", help="Do not save item JSON files")
    parser.add_argument("--no-skip-existing", action="store_true", help="Do not skip existing JSON/images; always re-download/overwrite")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG","INFO","WARNING","ERROR"], help="Logging level (default: INFO)")
    # Internal flag used when the script re-invokes itself for a one-time self-check
    parser.add_argument("--self-check-run", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    # Configure logging according to CLI flag
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s: %(message)s")

    # Determine base URL and output directory, with sensible defaults.
    default_collection = "bain"
    collection = args.collection if args.collection else default_collection
    default_base_url = f"https://www.loc.gov/collections/{collection}/"
    base_url = args.base_url if args.base_url else default_base_url
    # When `--collection` is used (or the default), place collection folders under the project's `output/` root
    output_dir = args.output_dir if args.output_dir else os.path.join("output", collection)

    recheck_needed = paginate_and_iterate_child_loc(
        base_url=base_url,
        child_key="results",
        count_c=args.count,
        start_sp=args.start,
        extra_params=None,
        stop_on_short_page=True,
        polite_delay_s=args.polite_delay,
        output_dir=output_dir,
        save_json=not args.no_save_json,
        download_images=not args.no_download_images,
        skip_existing=not args.no_skip_existing,
    )

    # If the pagination loop indicated that the next page fetch failed due to exhausting
    # retries, and this is NOT already a self-check run, spawn a one-time child process
    # to re-run the script for verification. Pass `--self-check-run` so the child won't
    # attempt to spawn again and create a loop.
    if recheck_needed and not args.self_check_run:
        try:
            cmd = [sys.executable, os.path.abspath(__file__)] + sys.argv[1:] + ["--self-check-run"]
            subprocess.Popen(cmd)
            logger.info(f"Spawned self-check subprocess: {cmd}")
        except Exception as e:
            logger.warning(f"Failed to spawn self-check subprocess: {e}")


if __name__ == "__main__":
    main()
