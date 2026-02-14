# Copyright (C) 2025
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

r"""Subject and HTML header sanitization for rss2email

This module provides a post-processing function to sanitize email subjects
and HTML headers by removing unwanted characters (like emojis) based on a 
configurable regex pattern.

Usage:
  Add to your config file:
  
  [DEFAULT]
  # Enable subject and HTML header sanitization
  sanitize-subject = True
  
  # Optional: Customize the sanitization pattern
  # This pattern keeps only Russian, English, and Kazakh letters, digits, spaces, and punctuation
  subject-sanitization-regex = [^a-zA-Zа-яА-ЯәғқңөұүһіӘҒҚҢӨҰҮҺІ0-9 .,!?:;()[\]{}"\'«»\-–—]
  
  # Set the post-processing function
  post-process = rss2email.post_process.sanitize_subject sanitize

This will remove emojis and other unwanted characters from:
- Email subject lines
- HTML headers (h1, h2, h3, h4, h5, h6) in the email body

This helps with email client compatibility, especially in dark mode,
while preserving the HTML structure and CSS.
"""

import re
import logging
from email.header import decode_header, make_header

# Get logger
from .. import LOG as _LOG

def sanitize(feed, parsed, entry, guid, message):
    """Sanitize the email subject and HTML content by removing unwanted characters.
    
    Uses the subject-sanitization-regex configuration option to determine
    which characters to remove from both subject and HTML content.
    
    Args:
        feed: The Feed instance
        parsed: The parsed feed
        entry: The feed entry
        guid: The entry guid
        message: The email message
        
    Returns:
        The modified message with sanitized subject and HTML content
    """
    # Check if subject sanitization is enabled
    try:
        if not feed.config.getboolean(feed.section, 'sanitize-subject', fallback=False):
            return message
    except (AttributeError, ValueError):
        # If the option doesn't exist or isn't a valid boolean, return the original message
        return message
    
    # Get the sanitization regex pattern
    try:
        pattern = feed.config.get(feed.section, 'subject-sanitization-regex',
                                  fallback=r'[^a-zA-Zа-яА-ЯәғқңөұүһіӘҒҚҢӨҰҮҺІ0-9 .,!?:;()[\]{}"\'«»\-–—]')
    except (AttributeError, ValueError):
        # Use default pattern if there's an error
        pattern = r'[^a-zA-Zа-яА-ЯәғқңөұүһіӘҒҚҢӨҰҮҺІ0-9 .,!?:;()[\]{}"\'«»\-–—]'
    
    # Compile the regex pattern for better performance
    regex = re.compile(pattern)
    
    # Sanitize the subject
    subject = message.get('Subject')
    if subject is not None:
        try:
            # Decode the subject if it's encoded
            if isinstance(subject, str):
                decoded_subject = subject
            else:
                decoded_subject = str(make_header(decode_header(subject)))
            
            # Log the original subject for debugging
            _LOG.debug(f'Original subject: {decoded_subject}')
            
            # Sanitize the subject
            sanitized_subject = regex.sub('', decoded_subject)
            
            # Log the sanitized subject for debugging
            _LOG.debug(f'Sanitized subject: {sanitized_subject}')
            
            # Update the message subject
            if sanitized_subject != decoded_subject:
                message.replace_header('Subject', sanitized_subject)
        except Exception as e:
            # Log any errors but don't break email delivery
            _LOG.error(f'Error sanitizing subject: {e}')
    
    # Sanitize HTML content (only in headers)
    try:
        # Get the message payload
        if message.is_multipart():
            for part in message.walk():
                if part.get_content_type() == 'text/html':
                    # Get the HTML content
                    html_content = part.get_payload(decode=True)
                    if html_content:
                        # Decode to string
                        html_str = html_content.decode('utf-8', errors='ignore')
                        
                        # Log original HTML for debugging
                        _LOG.debug(f'Original HTML content length: {len(html_str)}')
                        
                        # Sanitize only HTML headers (h1, h2, h3, h4, h5, h6)
                        import re as html_re
                        
                        def clean_headers(text):
                            # Pattern to match h1-h6 tags with their content
                            pattern = r'<(h[1-6])([^>]*)>(.*?)</\1>'
                            
                            def replace_header(match):
                                tag = match.group(1)  # h1, h2, etc.
                                attributes = match.group(2)  # attributes
                                content = match.group(3)  # content inside tag
                                
                                # Remove emoji spans and other unwanted HTML tags
                                # First remove <span class="emoji">...</span> tags
                                content = html_re.sub(r'<span[^>]*class="emoji"[^>]*>.*?</span>', '', content, flags=html_re.DOTALL)
                                
                                # Remove other common emoji-related spans
                                content = html_re.sub(r'<span[^>]*class="[^"]*emoji[^"]*"[^>]*>.*?</span>', '', content, flags=html_re.DOTALL)
                                
                                # Clean emojis and unwanted characters but preserve HTML tags
                                # First, remove common emoji patterns
                                emoji_patterns = [
                                    r'[\U0001F600-\U0001F64F]',  # Emoticons
                                    r'[\U0001F300-\U0001F5FF]',  # Misc Symbols and Pictographs
                                    r'[\U0001F680-\U0001F6FF]',  # Transport and Map
                                    r'[\U0001F1E0-\U0001F1FF]',  # Regional indicators
                                    r'[\U00002600-\U000026FF]',  # Misc symbols
                                    r'[\U00002700-\U000027BF]',  # Dingbats
                                    r'[\U0001F900-\U0001F9FF]',  # Supplemental Symbols and Pictographs
                                    r'[\U0001FA70-\U0001FAFF]',  # Symbols and Pictographs Extended-A
                                    r'[\U0001F018-\U0001F0F5]',  # Enclosed characters
                                    r'[\U0001F200-\U0001F2FF]',  # Enclosed CJK Letters and Months
                                    r'[\U0001F300-\U0001F5FF]',  # Misc symbols
                                    r'[\U0001F600-\U0001F64F]',  # Emoticons
                                    r'[\U0001F680-\U0001F6FF]',  # Transport
                                    r'[\U0001F700-\U0001F77F]',  # Alchemical Symbols
                                    r'[\U0001F780-\U0001F7FF]',  # Geometric Shapes Extended
                                    r'[\U0001F800-\U0001F8FF]',  # Supplemental Arrows-C
                                    r'[\U0001F900-\U0001F9FF]',  # Supplemental Symbols
                                    r'[\U0001FA00-\U0001FA6F]',  # Chess Symbols
                                    r'[\U0001FA70-\U0001FAFF]',  # Symbols and Pictographs Extended-A
                                    r'[\U0001FB00-\U0001FBFF]',  # Symbols for Legacy Computing
                                    r'[\U0001FC00-\U0001FCFF]',  # Symbols for Legacy Computing
                                    r'[\U0001FD00-\U0001FDFF]',  # Symbols for Legacy Computing
                                    r'[\U0001FE00-\U0001FE0F]',  # Variation Selectors
                                    r'[\U0001FE20-\U0001FE2F]',  # Combining Half Marks
                                    r'[\U0001FE30-\U0001FE4F]',  # CJK Compatibility Forms
                                    r'[\U0001FE50-\U0001FE6F]',  # Small Form Variants
                                    r'[\U0001FE70-\U0001FEFF]',  # Arabic Presentation Forms-B
                                    r'[\U0001FF00-\U0001FFFF]',  # Specials
                                ]
                                
                                # Remove emojis
                                for pattern in emoji_patterns:
                                    content = html_re.sub(pattern, '', content)
                                
                                # Clean up multiple spaces
                                content = html_re.sub(r'\s+', ' ', content)
                                
                                # Remove other unwanted characters but preserve HTML structure
                                # Keep only letters, numbers, spaces, punctuation, and HTML-safe characters
                                safe_pattern = r'[^a-zA-Zа-яА-ЯәғқңөұүһіӘҒҚҢӨҰҮҺІ0-9 .,!?:;()[\]{}"\'«»\-–—<>/=_]'
                                cleaned_content = html_re.sub(safe_pattern, '', content)
                                
                                return f'<{tag}{attributes}>{cleaned_content}</{tag}>'
                            
                            return html_re.sub(pattern, replace_header, text, flags=html_re.DOTALL)
                        
                        sanitized_html = clean_headers(html_str)
                        
                        # Log sanitized HTML for debugging
                        _LOG.debug(f'Sanitized HTML content length: {len(sanitized_html)}')
                        
                        # Update the HTML content
                        if sanitized_html != html_str:
                            part.set_payload(sanitized_html.encode('utf-8'))
                            _LOG.debug('HTML headers and emoji spans sanitized')
        else:
            # Single part message
            if message.get_content_type() == 'text/html':
                html_content = message.get_payload(decode=True)
                if html_content:
                    # Decode to string
                    html_str = html_content.decode('utf-8', errors='ignore')
                    
                    # Sanitize only HTML headers
                    import re as html_re
                    
                    def clean_headers(text):
                        # Pattern to match h1-h6 tags with their content
                        pattern = r'<(h[1-6])([^>]*)>(.*?)</\1>'
                        
                        def replace_header(match):
                            tag = match.group(1)  # h1, h2, etc.
                            attributes = match.group(2)  # attributes
                            content = match.group(3)  # content inside tag
                            
                            # Remove emoji spans and other unwanted HTML tags
                            # First remove <span class="emoji">...</span> tags
                            content = html_re.sub(r'<span[^>]*class="emoji"[^>]*>.*?</span>', '', content, flags=html_re.DOTALL)
                            
                            # Remove other common emoji-related spans
                            content = html_re.sub(r'<span[^>]*class="[^"]*emoji[^"]*"[^>]*>.*?</span>', '', content, flags=html_re.DOTALL)
                            
                            # Clean emojis and unwanted characters but preserve HTML tags
                            # First, remove common emoji patterns
                            emoji_patterns = [
                                r'[\U0001F600-\U0001F64F]',  # Emoticons
                                r'[\U0001F300-\U0001F5FF]',  # Misc Symbols and Pictographs
                                r'[\U0001F680-\U0001F6FF]',  # Transport and Map
                                r'[\U0001F1E0-\U0001F1FF]',  # Regional indicators
                                r'[\U00002600-\U000026FF]',  # Misc symbols
                                r'[\U00002700-\U000027BF]',  # Dingbats
                                r'[\U0001F900-\U0001F9FF]',  # Supplemental Symbols and Pictographs
                                r'[\U0001FA70-\U0001FAFF]',  # Symbols and Pictographs Extended-A
                                r'[\U0001F018-\U0001F0F5]',  # Enclosed characters
                                r'[\U0001F200-\U0001F2FF]',  # Enclosed CJK Letters and Months
                                r'[\U0001F300-\U0001F5FF]',  # Misc symbols
                                r'[\U0001F600-\U0001F64F]',  # Emoticons
                                r'[\U0001F680-\U0001F6FF]',  # Transport
                                r'[\U0001F700-\U0001F77F]',  # Alchemical Symbols
                                r'[\U0001F780-\U0001F7FF]',  # Geometric Shapes Extended
                                r'[\U0001F800-\U0001F8FF]',  # Supplemental Arrows-C
                                r'[\U0001F900-\U0001F9FF]',  # Supplemental Symbols
                                r'[\U0001FA00-\U0001FA6F]',  # Chess Symbols
                                r'[\U0001FA70-\U0001FAFF]',  # Symbols and Pictographs Extended-A
                                r'[\U0001FB00-\U0001FBFF]',  # Symbols for Legacy Computing
                                r'[\U0001FC00-\U0001FCFF]',  # Symbols for Legacy Computing
                                r'[\U0001FD00-\U0001FDFF]',  # Symbols for Legacy Computing
                                r'[\U0001FE00-\U0001FE0F]',  # Variation Selectors
                                r'[\U0001FE20-\U0001FE2F]',  # Combining Half Marks
                                r'[\U0001FE30-\U0001FE4F]',  # CJK Compatibility Forms
                                r'[\U0001FE50-\U0001FE6F]',  # Small Form Variants
                                r'[\U0001FE70-\U0001FEFF]',  # Arabic Presentation Forms-B
                                r'[\U0001FF00-\U0001FFFF]',  # Specials
                            ]
                            
                            # Remove emojis
                            for pattern in emoji_patterns:
                                content = html_re.sub(pattern, '', content)
                            
                            # Clean up multiple spaces
                            content = html_re.sub(r'\s+', ' ', content)
                            
                            # Remove other unwanted characters but preserve HTML structure
                            # Keep only letters, numbers, spaces, punctuation, and HTML-safe characters
                            safe_pattern = r'[^a-zA-Zа-яА-ЯәғқңөұүһіӘҒҚҢӨҰҮҺІ0-9 .,!?:;()[\]{}"\'«»\-–—<>/=_]'
                            cleaned_content = html_re.sub(safe_pattern, '', content)
                            
                            return f'<{tag}{attributes}>{cleaned_content}</{tag}>'
                        
                        return html_re.sub(pattern, replace_header, text, flags=html_re.DOTALL)
                    
                    sanitized_html = clean_headers(html_str)
                    
                    # Update the HTML content
                    if sanitized_html != html_str:
                        message.set_payload(sanitized_html.encode('utf-8'))
                        _LOG.debug('HTML headers and emoji spans sanitized')
    except Exception as e:
        # Log any errors but don't break email delivery
        _LOG.error(f'Error sanitizing HTML headers: {e}')
    
    return message