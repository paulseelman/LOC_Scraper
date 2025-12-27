import json
import logging
from pathlib import Path

import responses
import requests

from LOC_Scraper import process_item, _save_item_and_images


def test_process_item_logs(caplog):
    caplog.set_level(logging.INFO)
    caplog.clear()

    process_item({"title": "Hello Title", "url": "http://example.com/item"})

    assert any("Hello Title | http://example.com/item" in rec.message for rec in caplog.records)


def test_save_item_json_skip_logs(tmp_path, caplog):
    item = {"id": "abc123", "a": 1}
    out_dir = tmp_path / "out"
    folder = out_dir / "abc123"
    folder.mkdir(parents=True)

    # write identical existing JSON
    (folder / "item.json").write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")

    caplog.set_level(logging.INFO)
    _save_item_and_images(requests.Session(), item, str(out_dir), idx=1, save_json=True, download_images=False, skip_existing=True)

    assert any("Skipping JSON for abc123 (unchanged)" in rec.message for rec in caplog.records)


def test_save_item_json_update_logs(tmp_path, caplog):
    item = {"id": "abc123", "a": 2}
    out_dir = tmp_path / "out"
    folder = out_dir / "abc123"
    folder.mkdir(parents=True)

    # write different existing JSON
    (folder / "item.json").write_text(json.dumps({"id": "abc123", "a": 1}, ensure_ascii=False), encoding="utf-8")

    caplog.set_level(logging.INFO)
    _save_item_and_images(requests.Session(), item, str(out_dir), idx=1, save_json=True, download_images=False, skip_existing=True)

    assert any("Updated JSON for abc123" in rec.message for rec in caplog.records)


@responses.activate
def test_save_image_logs(tmp_path, caplog):
    item = {"id": "img1", "image": "https://images.example/test.jpg"}
    out_dir = tmp_path / "out"

    caplog.set_level(logging.INFO)

    # HEAD response
    responses.add(responses.HEAD, item["image"], headers={"Content-Length": "4", "Content-Type": "image/jpeg"}, status=200)
    # GET response for download
    responses.add(responses.GET, item["image"], body=b"abcd", status=200, content_type="image/jpeg")

    s = requests.Session()
    _save_item_and_images(s, item, str(out_dir), idx=1, save_json=False, download_images=True, skip_existing=True)

    assert any("Saved image" in rec.message for rec in caplog.records)
