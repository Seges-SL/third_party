# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""A file's text for the model, whatever the file is.

Printed text comes page by page from pns_base. A scan or a photo has none:
this agent's own vision chain transcribes it once. The same reading serves
a file dropped in the chat and an attachment of an Odoo record read with
``read_attachment``; the result is kept on the session as a document
(``turn_documents``) so later turns read it instead of transcribing again.
"""
import base64
import logging

from . import file_text, turn_documents
from .chatboo_product_icp import CHATBOO_AGENT_CODE

_logger = logging.getLogger(__name__)

PDF_TEXT_PAGES = 200
PDF_VISION_PAGES = 10
NO_TEXT = 'NONE'
# Raster formats a vision model decodes. Vector or icon formats make every
# provider reject the call.
VISION_MIMETYPES = (
    'image/jpeg', 'image/jpg', 'image/png',
    'image/gif', 'image/webp', 'image/bmp',
)


def transcribe_pages(env, pictures, agent_code=None, provider_id=None,
                     photos=False, tag='Chatboo'):
    """The text of each picture, read by this agent's vision chain. [] on failure.

    A scanned page is always transcribed. A photo only when its point is
    its text; for any other the model writes ``NO_TEXT``.
    """
    if not pictures:
        return []
    if photos:
        prompt = (
            'These are %d pictures. Begin each one with a line like "%s", '
            'counting from 1. If the picture is a document whose point is '
            'its text (a ticket, an invoice, a letter, a form, a screenshot '
            'of text), transcribe that text exactly as written, in its own '
            'language. Otherwise write only %s. No comments and no summary.'
            % (len(pictures), turn_documents.PAGE_MARK % 1, NO_TEXT)
        )
    else:
        prompt = (
            'Transcribe the text of these %d scanned pages exactly as written, '
            'in their own language. Begin each page with a line like "%s", '
            'counting from 1. No comments and no summary.'
            % (len(pictures), turn_documents.PAGE_MARK % 1)
        )
    try:
        code = env['ai.agent'].resolve_inference_agent_code(
            agent_code or CHATBOO_AGENT_CODE,
        )
        response = env['ai.execution.engine'].sudo()._chat_completion(
            code,
            [{'role': 'user', 'content': prompt}],
            images=pictures,
            provider_id=provider_id or None,
        )
        content = response['choices'][0]['message']['content']
    except Exception:
        _logger.warning('%s: transcription failed', tag, exc_info=True)
        return []
    if isinstance(content, list):
        content = ''.join(
            part.get('text', '') for part in content if isinstance(part, dict)
        )
    return turn_documents.split_pages(content, len(pictures))


def pdf_reading(env, raw, agent_code=None, provider_id=None, tag='Chatboo'):
    """``(page texts, pictures)`` of a PDF; None if ``raw`` is not a PDF.

    Printed text comes page by page from pns_base. A scan has none: the
    vision chain transcribes it once. When that fails, its pages come back
    as pictures for the caller to send with the turn.
    """
    from odoo.addons.pns_base.utils.pdf_io import (
        is_pdf, pdf_page_texts, pdf_pictures,
    )

    if not is_pdf(raw or b''):
        return None
    pages = pdf_page_texts(raw, pages=PDF_TEXT_PAGES)
    if pages:
        return pages, []
    pictures = [
        'data:image/jpeg;base64,%s' % base64.b64encode(jpeg).decode()
        for jpeg in pdf_pictures(raw, pages=PDF_VISION_PAGES)
    ]
    pages = transcribe_pages(
        env, pictures, agent_code=agent_code, provider_id=provider_id, tag=tag,
    )
    return (pages, []) if pages else ([], pictures)


def file_pages(env, name, mimetype, raw, agent_code=None, provider_id=None,
               tag='Chatboo'):
    """The pages of any file, as text. ``[]`` when nothing could be read.

    A PDF gives one page per page (printed or transcribed). A picture is
    transcribed as one page. Anything else goes through ``file_text``.
    """
    if not raw:
        return []
    reading = pdf_reading(
        env, raw, agent_code=agent_code, provider_id=provider_id, tag=tag,
    )
    if reading is not None:
        pages, _pictures = reading
        return pages if any(page.strip() for page in pages) else []
    mimetype = (mimetype or '').lower()
    if mimetype in VISION_MIMETYPES:
        picture = 'data:%s;base64,%s' % (mimetype, base64.b64encode(raw).decode())
        pages = transcribe_pages(
            env, [picture], agent_code=agent_code, provider_id=provider_id, tag=tag,
        )
        text = (pages[0] if pages else '').strip()
        return [text] if text and text != NO_TEXT else []
    text = file_text.file_text(
        name, mimetype, base64.b64encode(raw).decode(), ref=tag,
    )
    return [text] if (text or '').strip() else []
