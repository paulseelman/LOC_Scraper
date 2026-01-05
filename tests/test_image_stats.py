import os
import sys
from pathlib import Path

import LOC_Scraper


class DummyResp:
    def __init__(self, content: bytes = b"abc"):
        self._content = content
        self.status_code = 200
        self.headers = {}

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=8192):
        yield self._content


class DummySession:
    def get(self, url, stream=True, timeout=30, headers=None):
        return DummyResp(b"abc")

    def head(self, url, allow_redirects=True, timeout=20):
        class H:
            status_code = 200
            headers = {}

        return H()


def test_image_set_stats_increment_on_download(tmp_path, monkeypatch):
    LOC_Scraper._reset_image_session_stats()

    # patch head info to indicate an image content-type (so extension is added)
    monkeypatch.setattr(LOC_Scraper, "_image_head_info", lambda s, u: (None, None, "image/jpeg"))

    session = DummySession()

    item = {"title": "Test Item", "url": "http://example/item/1", "image": "http://example.org/image1.jpg"}

    LOC_Scraper._save_item_and_images(session, item, str(tmp_path), 1, save_json=False, download_images=True, skip_existing=True)

    # We downloaded one file (content length 3) -> one image set and 3 bytes
    assert LOC_Scraper._session_image_sets == 1
    assert LOC_Scraper._session_image_bytes == 3

    # File exists and has expected content (folder name is derived from item's 'url')
    folder = LOC_Scraper._sanitize_name(item['url'])
    item_dir = tmp_path / folder
    files = list(item_dir.iterdir())
    assert any(p.suffix for p in files)


def test_image_set_skipped_when_existing_matches(tmp_path, monkeypatch):
    LOC_Scraper._reset_image_session_stats()

    # Create an existing image file of size 4 in the folder the saver will use
    output_dir = tmp_path
    item = {"title": "Item with existing image", "image": "http://example.org/image.jpg"}
    folder = LOC_Scraper._sanitize_name(item['title'])
    item_dir = output_dir / folder
    item_dir.mkdir()
    dst = item_dir / "image.jpg"
    dst.write_bytes(b'abcd')

    # Make head info report same content length so the file will be skipped
    monkeypatch.setattr(LOC_Scraper, "_image_head_info", lambda s, u: (4, None, "image/jpeg"))

    session = DummySession()

    LOC_Scraper._save_item_and_images(session, item, str(output_dir), 1, save_json=False, download_images=True, skip_existing=True)

    # No downloads should have been counted
    assert LOC_Scraper._session_image_sets == 0
    assert LOC_Scraper._session_image_bytes == 0
