# -*- coding: utf-8 -*-
#
# This file is part of rss2email.
#
# rss2email is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 2 of the License, or (at your option) version 3 of
# the License.
#
# rss2email is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# rss2email.  If not, see <http://www.gnu.org/licenses/>.

"""Test for the subject sanitization feature."""

import configparser
import email.message
import unittest
from email.mime.text import MIMEText

from rss2email.post_process import sanitize_subject


class TestSanitizeSubject(unittest.TestCase):
    def setUp(self):
        class MockFeed:
            def __init__(self):
                self.config = configparser.ConfigParser()
                self.config['DEFAULT'] = {
                    'sanitize-subject': 'True',
                    'subject-sanitization-regex': (
                        r'[^a-zA-Zа-яА-ЯәғқңөұүһіӘҒҚҢӨҰҮҺІ0-9 .,!?:;()[\]{}"\'«»\-–—]'
                    ),
                }
                self.section = 'DEFAULT'

        self.feed = MockFeed()

    def test_sanitize_subject_with_unwanted_chars(self):
        message = email.message.EmailMessage()
        message['Subject'] = 'Test Subject with 😊 emoji and ★ symbols'

        processed_message = sanitize_subject.sanitize(
            feed=self.feed,
            parsed=None,
            entry=None,
            guid=None,
            message=message,
        )

        self.assertEqual(
            processed_message['Subject'],
            'Test Subject with  emoji and  symbols',
        )

    def test_sanitize_subject_with_allowed_chars(self):
        message = email.message.EmailMessage()
        message['Subject'] = 'Test Subject with Russian Привет and Kazakh Сәлем'

        processed_message = sanitize_subject.sanitize(
            feed=self.feed,
            parsed=None,
            entry=None,
            guid=None,
            message=message,
        )

        self.assertEqual(
            processed_message['Subject'],
            'Test Subject with Russian Привет and Kazakh Сәлем',
        )

    def test_sanitize_subject_disabled(self):
        self.feed.config['DEFAULT']['sanitize-subject'] = 'False'
        message = email.message.EmailMessage()
        message['Subject'] = 'Test Subject with 😊 emoji and ★ symbols'

        processed_message = sanitize_subject.sanitize(
            feed=self.feed,
            parsed=None,
            entry=None,
            guid=None,
            message=message,
        )

        self.assertEqual(
            processed_message['Subject'],
            'Test Subject with 😊 emoji and ★ symbols',
        )

    def test_sanitize_only_top_html_header_subject(self):
        status_url = 'https://mastodon.online/@vas3k/116113808650246603'
        external_url = 'https://vas3k.club/post/30890/'
        html = """<!DOCTYPE html>
<html>
  <body>
    <div class=\"entry\">
      <h1 class=\"header extra\"><a href=\"https://mastodon.online/@vas3k/116113808650246603\">Test 😊 subject</a></h1>
      <div class=\"body\">
        <h1>Body 😊 heading</h1>
        <p>Body link <a href=\"https://vas3k.club/post/30890/\">external</a></p>
      </div>
      <div class=\"footer\">
        <p>URL: <a href=\"https://mastodon.online/@vas3k/116113808650246603\">https://mastodon.online/@vas3k/116113808650246603</a></p>
      </div>
    </div>
  </body>
</html>
"""
        message = MIMEText(html, _subtype='html', _charset='utf-8')
        message['Subject'] = 'Test 😊 subject'

        processed_message = sanitize_subject.sanitize(
            feed=self.feed,
            parsed=None,
            entry=None,
            guid=None,
            message=message,
        )

        sanitized_html = processed_message.get_payload(decode=True).decode('utf-8')

        self.assertEqual(processed_message['Subject'], 'Test  subject')
        self.assertIn(
            '<h1 class="header extra"><a href="{}">Test  subject</a></h1>'.format(status_url),
            sanitized_html,
        )
        self.assertIn('<h1>Body 😊 heading</h1>', sanitized_html)
        self.assertIn(
            '<p>URL: <a href="{}">{}</a></p>'.format(status_url, status_url),
            sanitized_html,
        )
        self.assertIn(
            '<p>Body link <a href="{}">external</a></p>'.format(external_url),
            sanitized_html,
        )


if __name__ == '__main__':
    unittest.main()
