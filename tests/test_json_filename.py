import json
import os
import sys
from pathlib import Path

import requests

import LOC_Scraper


def test_json_named_after_tif_u_stem(tmp_path):
    item = {"id": "img-item", "image": "http://example.org/images/37158u.tif"}
    out = tmp_path

    LOC_Scraper._save_item_and_images(requests.Session(), item, str(out), 1, save_json=True, download_images=False, skip_existing=True)

    folder = out / LOC_Scraper._sanitize_name(item['id'])
    assert (folder / "37158.json").exists()
    j = json.loads((folder / "37158.json").read_text(encoding='utf-8'))
    assert j == item


def test_json_named_after_jpg_r_stem(tmp_path):
    item = {"id": "img-item2", "image": "http://example.org/images/37158r.jpg"}
    out = tmp_path

    LOC_Scraper._save_item_and_images(requests.Session(), item, str(out), 1, save_json=True, download_images=False, skip_existing=True)

    folder = out / LOC_Scraper._sanitize_name(item['id'])
    assert (folder / "37158.json").exists()
    j = json.loads((folder / "37158.json").read_text(encoding='utf-8'))
    assert j == item


def test_prefers_u_tif_over_r_jpg(tmp_path):
    item = {
        "id": "img-item3",
        "images": [
            "http://example.org/images/1234r.jpg",
            "http://example.org/images/37158u.tif",
        ],
    }
    out = tmp_path

    LOC_Scraper._save_item_and_images(requests.Session(), item, str(out), 1, save_json=True, download_images=False, skip_existing=True)

    folder = out / LOC_Scraper._sanitize_name(item['id'])
    assert (folder / "37158.json").exists()


def test_fallback_to_item_json_when_no_image_named(tmp_path):
    item = {"id": "noimg", "title": "No images here"}
    out = tmp_path

    LOC_Scraper._save_item_and_images(requests.Session(), item, str(out), 1, save_json=True, download_images=False, skip_existing=True)

    folder = out / LOC_Scraper._sanitize_name(item['id'])
    assert (folder / "item.json").exists()
