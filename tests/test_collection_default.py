import os
import sys

import LOC_Scraper


def test_default_uses_brady_handy(monkeypatch, tmp_path):
    captured = {}

    def fake_paginate(*args, **kwargs):
        captured['base_url'] = kwargs.get('base_url')
        captured['output_dir'] = kwargs.get('output_dir')
        return False

    monkeypatch.setattr(LOC_Scraper, 'paginate_and_iterate_child_loc', fake_paginate)
    monkeypatch.setattr(sys, 'argv', ["LOC_Scraper.py"])  # no args

    LOC_Scraper.main()

    assert captured['base_url'] == 'https://www.loc.gov/collections/brady-handy/'
    assert captured['output_dir'] == os.path.join('output', 'brady-handy')
