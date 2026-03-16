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

r"""Sanitize email subjects and the top HTML header."""

import re
from email.header import decode_header, make_header
from html import escape as _escape

from .. import LOG as _LOG

_DEFAULT_PATTERN = (
    r'[^a-zA-Zа-яА-ЯәғқңөұүһіӘҒҚҢӨҰҮҺІ0-9 .,!?:;()[\]{}"\'«»\-–—]'
)
_HEADER_PATTERN = re.compile(
    r'(?P<open><h1\b[^>]*>)(?P<content>.*?)(?P<close></h1>)',
    flags=re.IGNORECASE | re.DOTALL,
)
_CLASS_PATTERN = re.compile(
    r'\bclass\s*=\s*(?P<quote>["\'])(?P<value>.*?)(?P=quote)',
    flags=re.IGNORECASE | re.DOTALL,
)
_LINK_PATTERN = re.compile(
    r'(?P<open><a\b[^>]*>)(?P<content>.*?)(?P<close></a>)',
    flags=re.IGNORECASE | re.DOTALL,
)


def _decode_subject(subject):
    if isinstance(subject, str):
        return subject
    return str(make_header(decode_header(subject)))


def _sanitize_text(text, regex):
    return regex.sub('', text)


def _has_header_class(tag):
    match = _CLASS_PATTERN.search(tag)
    if not match:
        return False
    classes = re.split(r'\s+', match.group('value').strip())
    return 'header' in classes


def _replace_top_header_subject(html, subject):
    escaped_subject = _escape(subject, quote=False)
    for match in _HEADER_PATTERN.finditer(html):
        if not _has_header_class(match.group('open')):
            continue
        content = match.group('content')
        link = _LINK_PATTERN.search(content)
        if link:
            replacement = ''.join((
                content[:link.start()],
                link.group('open'),
                escaped_subject,
                link.group('close'),
                content[link.end():],
            ))
        else:
            replacement = escaped_subject
        return ''.join((
            html[:match.start()],
            match.group('open'),
            replacement,
            match.group('close'),
            html[match.end():],
        ))
    return html


def _iter_html_parts(message):
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == 'text/html':
                yield part
        return
    if message.get_content_type() == 'text/html':
        yield message


def _update_html_header(message, sanitized_subject):
    for part in _iter_html_parts(message):
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        charset = part.get_content_charset() or 'utf-8'
        html = payload.decode(charset, errors='ignore')
        sanitized_html = _replace_top_header_subject(html, sanitized_subject)
        if sanitized_html != html:
            if part['Content-Transfer-Encoding']:
                del part['Content-Transfer-Encoding']
            part.set_payload(sanitized_html, charset=charset)
            _LOG.debug('HTML header subject sanitized')


def sanitize(feed, parsed, entry, guid, message):
    """Sanitize the message subject and the top HTML header."""
    try:
        if not feed.config.getboolean(feed.section, 'sanitize-subject', fallback=False):
            return message
    except (AttributeError, ValueError):
        return message

    try:
        pattern = feed.config.get(
            feed.section,
            'subject-sanitization-regex',
            fallback=_DEFAULT_PATTERN,
        )
    except (AttributeError, ValueError):
        pattern = _DEFAULT_PATTERN

    regex = re.compile(pattern)
    subject = message.get('Subject')
    if subject is None:
        return message

    try:
        decoded_subject = _decode_subject(subject)
        sanitized_subject = _sanitize_text(decoded_subject, regex)
        _LOG.debug(f'Original subject: {decoded_subject}')
        _LOG.debug(f'Sanitized subject: {sanitized_subject}')
        if sanitized_subject != decoded_subject:
            message.replace_header('Subject', sanitized_subject)
            _update_html_header(message, sanitized_subject)
    except Exception as exc:
        _LOG.error(f'Error sanitizing subject: {exc}')

    return message
