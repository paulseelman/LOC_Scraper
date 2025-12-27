import logging
from LOC_Scraper import logger


def test_logger_present():
    assert isinstance(logger, logging.Logger)
