# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""SVG cards and link banners."""

import html
import json
import re
from urllib.parse import urlparse

from .relaxaicode_render_base import (
    _paints,
    _safe_card_href,
    _t,
)


def _link_host_label(href):
    """Hostname (or path) for the banner subtitle. Structural, not a domain list."""
    href = (href or '').strip()
    if href.startswith('/'):
        return (href.split('#', 1)[0] or '/')[:48]
    try:
        host = (urlparse(href).hostname or '').lower()
    except Exception:
        return ''
    if host.startswith('www.'):
        host = host[4:]
    return host


def _link_banner_mark_svg():
    """Decorative chain mark (not a fetched favicon)."""
    return (
        '<svg class="o_ai_link_banner_mark" viewBox="0 0 120 72" '
        'aria-hidden="true" focusable="false">'
        '<rect x="22" y="18" width="44" height="36" rx="8" fill="none" '
        'stroke="#0d6efd" stroke-width="3"/>'
        '<rect x="54" y="18" width="44" height="36" rx="8" fill="none" '
        'stroke="#5b6b7a" stroke-width="3"/>'
        '</svg>'
    )


def _link_banner_card_html(card):
    """Clickable banner (same gesture as the map card): preview + title + CTA."""
    href = _safe_card_href(
        card.get('url') or card.get('href') or card.get('link'),
    )
    if not href:
        return ''
    host = _link_host_label(href)
    title = (card.get('title') or host or href).strip()
    subtitle = (card.get('subtitle') or card.get('value') or '').strip()
    if not subtitle and host and host != title:
        subtitle = host
    safe_href = html.escape(href, quote=True)
    safe_title = html.escape(title)
    host_html = ''
    if subtitle:
        host_html = (
            '<span class="o_ai_link_banner_host">%s</span>'
            % html.escape(subtitle)
        )
    return (
        '<a class="o_ai_link_banner_card" href="%s" target="_blank" '
        'rel="noopener noreferrer" title="%s">'
        '<span class="o_ai_link_banner_preview" aria-hidden="true">'
        '%s</span>'
        '<span class="o_ai_link_banner_meta">'
        '<span class="o_ai_link_banner_title">%s</span>'
        '%s'
        '<span class="o_ai_link_banner_cta">%s '
        '<i class="fa fa-external-link" aria-hidden="true"></i></span>'
        '</span></a>'
    ) % (safe_href, safe_title, _link_banner_mark_svg(), safe_title, host_html,
         html.escape(_t('Open')))


_XMLID_RE = re.compile(r'^[a-z0-9_]+\.[A-Za-z0-9_.]+$')
_MODEL_RE = re.compile(r'^[a-z0-9_]+(\.[a-z0-9_]+)+$')
_FIELD_RE = re.compile(r'^[a-z_][a-z0-9_]*$')


def _form_card_payload(item):
    """``kind=form``: a form the person opens, fills in and saves (or not).

    The card carries the Odoo action (or model), the record to edit and the
    proposed values. Nothing is written here or on the click: the host opens
    the form and only the person's Save writes, with their own rights.
    """
    payload = {'kind': 'form'}
    for key in ('title', 'subtitle'):
        val = item.get(key)
        if val not in (None, ''):
            payload[key] = str(val)
    action = str(item.get('action') or '').strip()
    model = str(item.get('model') or '').strip()
    if action and _XMLID_RE.match(action):
        payload['action'] = action
    if model and _MODEL_RE.match(model):
        payload['model'] = model
    if not payload.get('action') and not payload.get('model'):
        return None
    try:
        res_id = int(item.get('res_id') or 0)
    except (TypeError, ValueError):
        res_id = 0
    if res_id > 0:
        payload['res_id'] = res_id
    values = {}
    raw_values = item.get('values')
    if isinstance(raw_values, dict) and not res_id:
        for key, val in raw_values.items():
            if not (isinstance(key, str) and _FIELD_RE.match(key)):
                continue
            if val is None or isinstance(val, (bool, int, float)):
                values[key] = val
            else:
                values[key] = str(val)
    if values:
        payload['values'] = values
    lines = item.get('lines')
    if isinstance(lines, (list, tuple)):
        kept = [str(line) for line in lines if line not in (None, '')]
        if kept:
            payload['lines'] = kept[:20]
    if not payload.get('title'):
        payload['title'] = payload.get('action') or payload.get('model')
    return payload


def _form_card_html(card):
    """Title, the person's lines, every field the form will get, and the button."""
    parts = ['<span class="o_ai_form_card_title">%s</span>' % html.escape(card['title'])]
    if card.get('subtitle'):
        parts.append(
            '<span class="o_ai_form_card_subtitle">%s</span>'
            % html.escape(card['subtitle'])
        )
    if card.get('lines'):
        parts.append('<ul class="o_ai_form_card_lines">%s</ul>' % ''.join(
            '<li>%s</li>' % html.escape(line) for line in card['lines']
        ))
    if card.get('values'):
        parts.append(
            '<span class="o_ai_form_card_fields">%s %s</span>' % (
                html.escape(_t('Fields filled in:')),
                html.escape(', '.join(sorted(card['values']))),
            )
        )
    label = _t('Open the record') if card.get('res_id') else _t('Open the form')
    parts.append(
        '<a href="#" role="button" class="o_ai_form_card_open">'
        '<i class="fa fa-pencil-square-o" aria-hidden="true"></i> %s</a>'
        % html.escape(label)
    )
    parts.append(
        '<span class="o_ai_form_card_note">%s</span>'
        % html.escape(_t('Nothing is saved until you press Save.'))
    )
    return ''.join(parts)


def _normalize_clock_iso(iso, tz_name):
    """Load ``user_time.normalize_clock_iso`` (Odoo package or file path)."""
    try:
        from .user_time import normalize_clock_iso
        return normalize_clock_iso(iso, tz_name)
    except ImportError:
        import importlib.util
        import os
        path = os.path.join(os.path.dirname(__file__), 'user_time.py')
        spec = importlib.util.spec_from_file_location('_pns_user_time', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.normalize_clock_iso(iso, tz_name)


def collect_svg_cards(result, render_context=None):
    """Card dicts from ``card`` / ``cards``. Clock without ``iso`` is dropped.

    Naive clock ``iso`` = process clock (UTC). The card's timezone
    (``tz``) wins; the session ``user_tz`` only if the card has no ``tz``.
    """
    if not isinstance(result, dict):
        return []
    ctx = render_context or {}
    user_tz = (ctx.get('user_tz') or '').strip() or None
    raw = []
    cards = result.get('cards')
    if isinstance(cards, list):
        raw.extend(cards)
    card = result.get('card')
    if isinstance(card, dict):
        raw.append(card)
    elif isinstance(card, list):
        raw.extend(card)
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        kind = str(item.get('kind') or 'fact').strip().lower() or 'fact'
        if kind == 'form':
            payload = _form_card_payload(item)
            if payload:
                out.append(payload)
            continue
        payload = {'kind': kind}
        for key in (
            'title', 'value', 'unit', 'tz', 'iso',
            'url', 'href', 'link', 'subtitle',
        ):
            val = item.get(key)
            if val not in (None, ''):
                payload[key] = str(val)
        if kind == 'link':
            href = _safe_card_href(
                payload.get('url') or payload.get('href') or payload.get('link'),
            )
            if not href:
                continue
            payload['url'] = href
            payload.pop('href', None)
            payload.pop('link', None)
            if not payload.get('title'):
                payload['title'] = _link_host_label(href) or href
            out.append(payload)
            continue
        if kind == 'clock' and not payload.get('iso'):
            continue
        if kind == 'clock':
            try:
                iso_out, tz_out = _normalize_clock_iso(
                    payload.get('iso'),
                    (payload.get('tz') or '').strip() or user_tz,
                )
                if iso_out:
                    payload['iso'] = iso_out
                if tz_out:
                    payload['tz'] = tz_out
            except Exception:
                pass
        if kind != 'clock' and not payload.get('title') and not payload.get('value'):
            continue
        out.append(payload)
    return out


@_paints
def render_svg_cards_html(result, render_context=None):
    """HTML envelope ``data-ai-card``; the host hydrates clock/fact SVG.

    ``kind=link`` is a real ``<a>`` banner (like the map card), painted here
    so it works without JS; the envelope remains for client re-hydrate.
    """
    cards = collect_svg_cards(result, render_context=render_context)
    if not cards:
        return ''
    parts = []
    for card in cards:
        try:
            payload = json.dumps(
                card, ensure_ascii=False, separators=(',', ':'), default=str,
            )
        except (TypeError, ValueError):
            continue
        attr = html.escape(payload, quote=True)
        if card.get('kind') == 'form':
            parts.append(
                '<div class="o_ai_svg_card o_ai_form_card" '
                'data-ai-card="%s">%s</div>'
                % (attr, _form_card_html(card))
            )
            continue
        if card.get('kind') == 'link':
            inner = _link_banner_card_html(card)
            if not inner:
                continue
            parts.append(
                '<div class="o_ai_svg_card o_ai_link_banner" '
                'data-ai-card="%s">%s</div>'
                % (attr, inner)
            )
            continue
        parts.append(
            '<div class="o_ai_svg_card" data-ai-card="%s"></div>'
            % attr
        )
    if not parts:
        return ''
    return '<div class="o_ai_svg_cards">%s</div>' % ''.join(parts)
