# run_doctests.py

import unittest
import doctest
from . import scrape_html


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(scrape_html))
    return tests
