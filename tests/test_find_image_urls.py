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


def test_constructs_loc_master_tif_from_service_r_jpg():
    jpg = "https://tile.loc.gov/storage-services/service/pnp/cph/3b20000/3b25000/3b25000/3b25004r.jpg"
    expected_tif = "https://tile.loc.gov/storage-services/master/pnp/cph/3b20000/3b25000/3b25000/3b25004u.tif"

    urls = _find_image_urls(jpg)
    assert jpg in urls
    assert expected_tif in urls
