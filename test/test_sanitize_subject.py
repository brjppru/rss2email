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

"""Test for the subject sanitization feature
"""

import unittest
import configparser
import email.message

from rss2email.post_process import sanitize_subject

class TestSanitizeSubject(unittest.TestCase):
    def setUp(self):
        # Create a mock feed object with config
        class MockFeed:
            def __init__(self):
                self.config = configparser.ConfigParser()
                self.config['DEFAULT'] = {
                    'sanitize-subject': 'True',
                    'subject-sanitization-regex': r'[^a-zA-Zа-яА-ЯәғқңөұүһіӘҒҚҢӨҰҮҺІ0-9 .,!?:;()[\]{}"\'«»\-–—]'
                }
                self.section = 'DEFAULT'
        
        self.feed = MockFeed()
        
    def test_sanitize_subject_with_unwanted_chars(self):
        """Test that unwanted characters are removed from the subject"""
        # Create a message with a subject containing unwanted characters
        message = email.message.EmailMessage()
        message['Subject'] = 'Test Subject with 😊 emoji and ★ symbols'
        
        # Process the message
        processed_message = sanitize_subject.sanitize(
            feed=self.feed,
            parsed=None,
            entry=None,
            guid=None,
            message=message
        )
        
        # Check that the subject was sanitized
        self.assertEqual(
            processed_message['Subject'],
            'Test Subject with  emoji and  symbols'
        )
    
    def test_sanitize_subject_with_allowed_chars(self):
        """Test that allowed characters are preserved in the subject"""
        # Create a message with a subject containing only allowed characters
        message = email.message.EmailMessage()
        message['Subject'] = 'Test Subject with Russian Привет and Kazakh Сәлем'
        
        # Process the message
        processed_message = sanitize_subject.sanitize(
            feed=self.feed,
            parsed=None,
            entry=None,
            guid=None,
            message=message
        )
        
        # Check that the subject was not changed
        self.assertEqual(
            processed_message['Subject'],
            'Test Subject with Russian Привет and Kazakh Сәлем'
        )
    
    def test_sanitize_subject_disabled(self):
        """Test that subject is not sanitized when the feature is disabled"""
        # Disable sanitization
        self.feed.config['DEFAULT']['sanitize-subject'] = 'False'
        
        # Create a message with a subject containing unwanted characters
        message = email.message.EmailMessage()
        message['Subject'] = 'Test Subject with 😊 emoji and ★ symbols'
        
        # Process the message
        processed_message = sanitize_subject.sanitize(
            feed=self.feed,
            parsed=None,
            entry=None,
            guid=None,
            message=message
        )
        
        # Check that the subject was not changed
        self.assertEqual(
            processed_message['Subject'],
            'Test Subject with 😊 emoji and ★ symbols'
        )

if __name__ == '__main__':
    unittest.main()