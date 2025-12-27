from LOC_Scraper import _find_image_urls


def test_find_image_urls_nested_and_query_and_case():
    obj = {
        "images": [
            {"url": "http://example.com/photo.JPG?size=large"},
            "https://cdn.example.org/path/image.png"
        ],
        "other": {
            "thumb": "http://example.com/thumb.jpeg"
        }
    }

    urls = _find_image_urls(obj)
    assert "http://example.com/photo.JPG?size=large" in urls
    assert "https://cdn.example.org/path/image.png" in urls
    assert "http://example.com/thumb.jpeg" in urls
