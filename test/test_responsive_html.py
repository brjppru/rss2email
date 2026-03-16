#!/usr/bin/env python3

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import rss2email.feed as _rss2email_feed


class TestResponsiveHtml(unittest.TestCase):
    def setUp(self):
        self.feed = _rss2email_feed.Feed(name='test-feed')

    def test_large_image_is_constrained_without_fixed_dimensions(self):
        html = (
            '<img src="https://example.com/image.jpg" width="1920" height="1080" '
            'style="max-width:none; width:1920px; height:1080px" />'
        )

        normalized = self.feed._normalize_html_for_email(html)

        self.assertNotIn('width="1920"', normalized)
        self.assertNotIn('height="1080"', normalized)
        self.assertNotIn('max-width:none', normalized)
        self.assertNotIn('width:1920px', normalized)
        self.assertNotIn('height:1080px', normalized)
        self.assertIn('max-width: 95% !important', normalized)
        self.assertIn('width: auto !important', normalized)
        self.assertIn('height: auto !important', normalized)
        self.assertIn('display: block', normalized)

    def test_small_image_is_not_stretched(self):
        html = '<img src="https://example.com/small.jpg" width="320" height="200" />'

        normalized = self.feed._normalize_html_for_email(html)

        self.assertIn('max-width: 95% !important', normalized)
        self.assertIn('width: auto !important', normalized)
        self.assertNotRegex(normalized, r'(?<!max-)width: 95%')
        self.assertNotIn('min-width: 95%', normalized)

    def test_container_width_is_removed_without_touching_theme_styles(self):
        html = (
            '<div class="wp-caption" style="color:#e0e0e0; background-color:transparent; '
            'width: 1930px; text-align:center; clear:both"></div>'
        )

        normalized = self.feed._normalize_html_for_email(html)

        self.assertNotIn('width: 1930px', normalized)
        self.assertIn('color: #e0e0e0', normalized)
        self.assertIn('background-color: transparent', normalized)
        self.assertIn('text-align: center', normalized)
        self.assertIn('clear: both', normalized)
        self.assertIn('max-width: 95% !important', normalized)
        self.assertIn('width: auto !important', normalized)
        self.assertIn('box-sizing: border-box', normalized)

    def test_wp_caption_fragment_is_normalized(self):
        html = (
            '<div class="wp-caption alignnone" id="attachment_1" style="width: 2570px;">'
            '<img src="https://example.com/image.jpg" width="2560" height="2101" />'
            '</div>'
        )

        normalized = self.feed._normalize_html_for_email(html)

        self.assertNotIn('width: 2570px', normalized)
        self.assertNotIn('width="2560"', normalized)
        self.assertNotIn('height="2101"', normalized)
        self.assertIn('max-width: 95% !important', normalized)
        self.assertNotRegex(normalized, r'(?<!max-)width: 95%')


if __name__ == '__main__':
    unittest.main()
