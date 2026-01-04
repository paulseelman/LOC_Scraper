import os
import sys

import LOC_Scraper


def test_main_derives_base_and_output_from_collection(monkeypatch, tmp_path):
    captured = {}

    def fake_paginate(*args, **kwargs):
        captured['base_url'] = kwargs.get('base_url')
        captured['output_dir'] = kwargs.get('output_dir')
        return False

    monkeypatch.setattr(LOC_Scraper, 'paginate_and_iterate_child_loc', fake_paginate)
    monkeypatch.setattr(sys, 'argv', ["LOC_Scraper.py", "--collection", "brady-handy"])

    LOC_Scraper.main()

    assert captured['base_url'] == 'https://www.loc.gov/collections/brady-handy/'
    assert captured['output_dir'] == 'brady-handy'


def test_explicit_flags_take_precedence(monkeypatch):
    captured = {}

    def fake_paginate(*args, **kwargs):
        captured['base_url'] = kwargs.get('base_url')
        captured['output_dir'] = kwargs.get('output_dir')
        return False

    monkeypatch.setattr(LOC_Scraper, 'paginate_and_iterate_child_loc', fake_paginate)
    monkeypatch.setattr(sys, 'argv', [
        "LOC_Scraper.py",
        "--collection", "bain",
        "--base-url", "https://example.org/custom/",
        "--output-dir", "my-output",
    ])

    LOC_Scraper.main()

    assert captured['base_url'] == 'https://example.org/custom/'
    assert captured['output_dir'] == 'my-output'
