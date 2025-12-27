import responses
import requests
from LOC_Scraper import _image_head_info


@responses.activate
def test_image_head_info_head_ok():
    url = "https://images.example/test.jpg"
    responses.add(responses.HEAD, url, headers={"Content-Length": "123", "Last-Modified": "Wed, 21 Oct 2015 07:28:00 GMT", "Content-Type": "image/jpeg"}, status=200)
    s = requests.Session()
    clen, lm, ctype = _image_head_info(s, url)
    assert clen == 123
    assert isinstance(lm, float)
    assert ctype and ctype.startswith("image/jpeg")


@responses.activate
def test_image_head_info_head_405_fallback_get():
    url = "https://images.example/test2.jpg"
    responses.add(responses.HEAD, url, status=405)
    responses.add(responses.GET, url, headers={"Content-Length": "10", "Content-Type": "image/png"}, status=200)
    s = requests.Session()
    clen, lm, ctype = _image_head_info(s, url)
    assert clen == 10
    assert ctype and ctype.startswith("image/png")
