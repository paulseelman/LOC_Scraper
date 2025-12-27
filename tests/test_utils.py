import hashlib

from LOC_Scraper import _sanitize_name, _compute_file_hash


def test_sanitize_name_replaces_and_truncate():
    assert _sanitize_name("Title: with / weird * chars") == "Title_with_weird_chars"

    longname = "a" * 200
    res = _sanitize_name(longname, max_len=50)
    assert len(res) <= 50


def test_compute_file_hash(tmp_path):
    p = tmp_path / "f"
    content = b"hello world"
    p.write_bytes(content)
    expected = hashlib.sha256(content).hexdigest()
    assert _compute_file_hash(p) == expected
