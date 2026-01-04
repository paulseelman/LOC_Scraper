import sys
import os
import subprocess

import LOC_Scraper


def test_paginate_returns_recheck_on_fetch_failure(monkeypatch, tmp_path):
    # fake fetch: page 1 returns a full page, page 2 raises the RuntimeError indicating retry exhaustion
    def fake_fetch(session, base_url, page_sp, count_c, extra_params=None, timeout_s=20, max_retries=4):
        if page_sp == 1:
            # return a page with `count_c` items so the paginator will attempt next page
            return {"results": [{"id": "1"} for _ in range(count_c)]}
        raise RuntimeError(f"Failed to fetch/parse JSON after {max_retries} retries (sp={page_sp}, c={count_c}). Last error: simulated")

    monkeypatch.setattr(LOC_Scraper, "fetch_json_page", fake_fetch)
    # Avoid network and file writes
    monkeypatch.setattr(LOC_Scraper, "_save_item_and_images", lambda *a, **k: None)

    # Run paginator; expect it to return True for recheck_needed
    res = LOC_Scraper.paginate_and_iterate_child_loc(
        base_url="https://example.org/collections/test/",
        child_key="results",
        count_c=2,
        start_sp=1,
        extra_params=None,
        stop_on_short_page=False,
        polite_delay_s=0.0,
        output_dir=str(tmp_path),
        save_json=False,
        download_images=False,
        skip_existing=True,
    )

    assert res is True


def test_main_spawns_subprocess_when_needed(monkeypatch, tmp_path):
    # simulate that paginator returned recheck_needed
    monkeypatch.setattr(LOC_Scraper, "paginate_and_iterate_child_loc", lambda *a, **k: True)

    calls = {}

    class DummyPopen:
        def __init__(self, cmd):
            calls['cmd'] = cmd

    monkeypatch.setattr(subprocess, "Popen", DummyPopen)

    # Provide simple argv so parsing works
    monkeypatch.setattr(sys, "argv", ["LOC_Scraper.py", "--base-url", "https://example.org/", "--output-dir", str(tmp_path)])

    LOC_Scraper.main()

    assert 'cmd' in calls
    cmd = calls['cmd']
    # Ensure we spawn Python executable and the script path and that --self-check-run is present
    assert cmd[0].endswith(('python', 'python3', 'python3.11', 'python3.12')) or os.path.basename(cmd[0]).startswith('python')
    assert os.path.abspath(LOC_Scraper.__file__) in cmd
    assert '--self-check-run' in cmd
