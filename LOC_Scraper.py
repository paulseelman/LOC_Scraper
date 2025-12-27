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
        print(f"{title} | {url}")
    else:
        print(json.dumps(item, ensure_ascii=False))


def _find_image_urls(obj: Any) -> List[str]:
    """
    Recurse into the item dict/list and return list of discovered image URLs.
    Simple heuristic: strings starting with http and ending with a common image extension.
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
        lower = obj.lower().split('?', 1)[0]
        if lower.startswith('http') and lower.endswith(image_exts):
            urls.add(obj)
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
                        print(f"Skipping JSON for {folder_name} (unchanged)")
                    else:
                        json.dump(item, existing_json_path.open('w', encoding='utf-8'), ensure_ascii=False, indent=2)
                        print(f"Updated JSON for {folder_name}")
                except (ValueError, OSError):
                    # if existing file is unreadable, overwrite
                    json.dump(item, existing_json_path.open('w', encoding='utf-8'), ensure_ascii=False, indent=2)
                    print(f"Wrote JSON for {folder_name} (replaced corrupted file)")
            else:
                with open(existing_json_path, 'w', encoding='utf-8') as fh:
                    json.dump(item, fh, ensure_ascii=False, indent=2)
        except OSError as e:
            print(f"Warning: failed to write JSON for {folder_name}: {e}")

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
                                print(f"Skipping image (exists, same size): {dst}")
                                skipped = True
                        if not skipped and lm is not None:
                            # compare file mtime to last-modified
                            if dst.stat().st_mtime >= lm:
                                print(f"Skipping image (exists, not older): {dst}")
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
                                        print(f"Skipping image (exists, identical content): {dst}")
                                        skipped = True
                                    else:
                                        # move into place (overwrite)
                                        tmp_path.replace(dst)
                                        print(f"Replaced image (content changed): {dst}")
                                        saved += 1
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
                        tmp_path.replace(dst_final)
                        print(f"Saved image: {dst_final}")
                        saved += 1
                    finally:
                        # cleanup if something went wrong and tmpf still exists
                        if 'tmp_path' in locals() and tmp_path.exists() and not tmp_path.samefile(dst if dst.exists() else tmp_path):
                            try:
                                tmp_path.unlink()
                            except Exception:
                                pass

            except requests.RequestException as e:
                print(f"Warning: failed to download {url}: {e}")


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

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    with requests.Session() as session:
        while True:
            data = fetch_json_page(
                session=session,
                base_url=base_url,
                page_sp=sp,
                count_c=count_c,
                extra_params=extra_params,
            )

            items = get_child_list(data, child_key)

            if not items:
                print(f"Stopping: no '{child_key}' items found at sp={sp}. Total processed: {total_processed}")
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
                    print(f"Warning: error saving item {total_processed + 1}: {e}")

                total_processed += 1
                if polite_delay_s > 0:
                    time.sleep(polite_delay_s)

            print(f"Processed sp={sp}: {len(items)} items (total {total_processed})")

            if stop_on_short_page and len(items) < count_c:
                print(f"Stopping: sp={sp} returned {len(items)} (< {count_c}). Total processed: {total_processed}")
                break

            sp += 1

            # if polite_delay_s > 0:
            #     time.sleep(polite_delay_s)


def main():
    parser = argparse.ArgumentParser(description="Iterate LoC collection, save item JSON and images.")
    parser.add_argument("--base-url", default="https://www.loc.gov/collections/bain/", help="Base LoC collection URL")
    parser.add_argument("--output-dir", default="output", help="Directory to save items and images")
    parser.add_argument("--count", type=int, default=25, help="Items per page (c)")
    parser.add_argument("--start", type=int, default=1, help="Starting page (sp)")
    parser.add_argument("--polite-delay", type=float, default=5.0, help="Delay between items (seconds)")
    parser.add_argument("--no-download-images", action="store_true", help="Do not download images")
    parser.add_argument("--no-save-json", action="store_true", help="Do not save item JSON files")
    parser.add_argument("--no-skip-existing", action="store_true", help="Do not skip existing JSON/images; always re-download/overwrite")
    args = parser.parse_args()

    paginate_and_iterate_child_loc(
        base_url=args.base_url,
        child_key="results",
        count_c=args.count,
        start_sp=args.start,
        extra_params=None,
        stop_on_short_page=True,
        polite_delay_s=args.polite_delay,
        output_dir=args.output_dir,
        save_json=not args.no_save_json,
        download_images=not args.no_download_images,
        skip_existing=not args.no_skip_existing,
    )


if __name__ == "__main__":
    main()
