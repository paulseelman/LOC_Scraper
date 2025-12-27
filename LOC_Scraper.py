import json
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

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


def paginate_and_iterate_child_loc(
    base_url: str,
    child_key: str = "results",
    count_c: int = 100,
    start_sp: int = 1,
    extra_params: Optional[Dict[str, Any]] = None,
    stop_on_short_page: bool = True,
    polite_delay_s: float = 0.0,
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
    """
    sp = start_sp
    total_processed = 0

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
    # Example URL scheme you provided:
    # https://www.loc.gov/collections/bain/?fo=json&c=100&sp=1
    base_url = "https://www.loc.gov/collections/bain/"

    paginate_and_iterate_child_loc(
        base_url=base_url,
        child_key="results",  # LoC JSON commonly uses 'results'
        count_c=100,
        start_sp=1,
        extra_params=None,    # add other LoC params here if you want
        stop_on_short_page=True,
        polite_delay_s=0.25,   # consider 0.1–0.25 if you want to be gentle
    )


if __name__ == "__main__":
    main()
