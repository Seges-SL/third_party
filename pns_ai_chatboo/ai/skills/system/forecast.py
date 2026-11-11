# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Weather forecast from Open-Meteo, a site on the URL whitelist.

Three rounds, told apart by ``previous_result``: geocode each place, fetch
one forecast per place, present. The engine only runs the ``fetch_url``
steps; the parameter reader already turned the user's words into a place,
an ISO start date and a number of days.
"""
import json
import re
from datetime import date, datetime, timedelta

_DAILY = (
    'temperature_2m_max,temperature_2m_min,precipitation_sum,'
    'windspeed_10m_max,uv_index_max,weathercode,sunrise,sunset'
)
_GEO_HOST = 'geocoding-api.open-meteo.com'
_FC_HOST = 'api.open-meteo.com/v1/forecast'
_URL_SAFE = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~'


def _urlq(text):
    return ''.join(
        ch if ch in _URL_SAFE else ''.join('%%%02X' % b for b in ch.encode('utf-8'))
        for ch in (text or '')
    )


def _unquote(text):
    raw = str(text or '').replace('+', ' ')
    buf = bytearray()
    i = 0
    while i < len(raw):
        if raw[i] == '%' and i + 3 <= len(raw):
            try:
                buf.append(int(raw[i + 1:i + 3], 16))
                i += 3
                continue
            except ValueError:
                pass
        buf.extend(raw[i].encode('utf-8'))
        i += 1
    return buf.decode('utf-8', 'replace')


def _split_place(raw):
    """'Paris (France)' -> ('Paris', 'France'). The hint picks among homonyms."""
    text = str(raw or '').strip()
    hint = None
    found = re.search(r'\(([^)]*)\)', text)
    if found:
        hint = found.group(1).strip() or None
        text = (text[:found.start()] + ' ' + text[found.end():]).strip()
    return re.sub(r'\s+', ' ', text).strip(' ,.;'), hint


def _pick(results, hint):
    if not results:
        return None
    wanted = re.sub(r'[^a-z0-9 ]', '', str(hint or '').lower()).strip()
    if wanted:
        for item in results:
            for key in ('admin1', 'admin2', 'country', 'country_code'):
                got = re.sub(r'[^a-z0-9 ]', '', str(item.get(key) or '').lower()).strip()
                if not got:
                    continue
                if got == wanted or (
                    min(len(got), len(wanted)) > 2 and (wanted in got or got in wanted)
                ):
                    return item
    return results[0]


def _bodies(prev, host):
    out = []
    for item in prev or []:
        if not isinstance(item, dict) or host not in str(item.get('url') or ''):
            continue
        body = item.get('body')
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except ValueError:
                body = None
        out.append((item, body if isinstance(body, dict) else None))
    return out


def _sky(code):
    """WMO weather code -> emoji and label. Inside a def: a long module-level
    literal is taken for pasted data and rebuilt through JSON (int keys lost)."""
    table = {
        0: ('Clear', '\u2600\ufe0f'), 1: ('Mainly clear', '\U0001f324\ufe0f'),
        2: ('Partly cloudy', '\u26c5'), 3: ('Overcast', '\u2601\ufe0f'),
        45: ('Fog', '\U0001f32b\ufe0f'), 48: ('Fog', '\U0001f32b\ufe0f'),
        51: ('Drizzle', '\U0001f326\ufe0f'), 53: ('Drizzle', '\U0001f326\ufe0f'),
        55: ('Drizzle', '\U0001f326\ufe0f'), 61: ('Rain', '\U0001f327\ufe0f'),
        63: ('Rain', '\U0001f327\ufe0f'), 65: ('Heavy rain', '\U0001f327\ufe0f'),
        71: ('Snow', '\u2744\ufe0f'), 73: ('Snow', '\u2744\ufe0f'),
        75: ('Heavy snow', '\u2744\ufe0f'), 80: ('Showers', '\U0001f326\ufe0f'),
        81: ('Showers', '\U0001f326\ufe0f'), 82: ('Showers', '\U0001f326\ufe0f'),
        95: ('Thunderstorm', '\u26c8\ufe0f'), 96: ('Thunderstorm', '\u26c8\ufe0f'),
        99: ('Thunderstorm', '\u26c8\ufe0f'),
    }
    try:
        label, emoji = table.get(int(code), ('', ''))
    except (TypeError, ValueError):
        return ''
    return ('%s %s' % (emoji, label)).strip()


def _cell(values, i, suffix=''):
    if i >= len(values) or values[i] is None:
        return ''
    return '%g%s' % (float(values[i]), suffix)


def _rows(daily):
    times = daily.get('time') or []
    codes = daily.get('weathercode') or daily.get('weather_code') or []
    rows = []
    for i, day in enumerate(times):
        rise = (daily.get('sunrise') or [''] * len(times))[i] or ''
        sset = (daily.get('sunset') or [''] * len(times))[i] or ''
        rows.append({
            'Date': datetime.strptime(str(day)[:10], '%Y-%m-%d').strftime('%a %d/%m'),
            'Sky': _sky(codes[i] if i < len(codes) else None),
            'Max': _cell(daily.get('temperature_2m_max') or [], i, '\u00b0'),
            'Min': _cell(daily.get('temperature_2m_min') or [], i, '\u00b0'),
            'Rain mm': _cell(daily.get('precipitation_sum') or [], i),
            'Wind km/h': _cell(daily.get('windspeed_10m_max') or [], i),
            'UV': _cell(daily.get('uv_index_max') or [], i),
            'Sunrise': rise[11:16],
            'Sunset': sset[11:16],
        })
    return rows


def _notice(text):
    return {'formatted_text': '<p class="text-muted">%s</p>' % text, '__return_direct__': True}


try:
    _place = place
except NameError:
    _place = None
try:
    _start = date.fromisoformat(str(start)[:10])
except (NameError, TypeError, ValueError):
    _start = date.today()
try:
    _days = int(days)
except (NameError, TypeError, ValueError):
    _days = 7
_days = max(1, min(16, _days))
_end = _start + timedelta(days=_days - 1)

if not str(_place or '').strip():
    _region = company.state_id.name if company.state_id else ''
    _region = _region or (company.country_id.name if company.country_id else '')
    if company.city:
        _place = '%s (%s)' % (company.city, _region) if _region else company.city
    else:
        _place = _region
_places = [p.strip() for p in re.split(r'[,;|]+', str(_place or '')) if p.strip()]

try:
    _prev = previous_result
except NameError:
    _prev = None
_geo = _bodies(_prev, _GEO_HOST)
_fc = _bodies(_prev, _FC_HOST)

if _fc:
    _found = []
    for _item, _body in _fc:
        if _body and _body.get('daily'):
            _m = re.search(r'[?&]city=([^&]+)', str(_item.get('url') or ''))
            _found.append((_unquote(_m.group(1)) if _m else '', _rows(_body['daily'])))
    if not _found:
        result = _notice('Open-Meteo sent no forecast for %s.' % ', '.join(_places))
    elif len(_found) == 1:
        result = {
            'summary': 'Weather · %s · %s to %s (Open-Meteo).' % (_found[0][0], _start, _end),
            'data': _found[0][1],
        }
    else:
        result = {
            'summary': 'Weather · %s to %s (Open-Meteo).' % (_start, _end),
            'groups': [{'title': name, 'rows': rows} for name, rows in _found],
        }
    result['__return_direct__'] = True
    result['__no_footer__'] = True
elif _geo:
    _steps = []
    for _i, (_item, _body) in enumerate(_geo):
        _hint = _split_place(_places[_i])[1] if _i < len(_places) else None
        _hit = _pick((_body or {}).get('results') or [], _hint)
        if not _hit or _hit.get('latitude') is None:
            continue
        _steps.append({
            'op': 'fetch_url',
            'name': _hit.get('name') or _item.get('name') or '',
            'url': (
                'https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s'
                '&daily=%s&timezone=%s&start_date=%s&end_date=%s&city=%s'
            ) % (
                _hit['latitude'], _hit['longitude'], _DAILY,
                _urlq(_hit.get('timezone') or 'auto'), _start, _end,
                _urlq(_hit.get('name') or ''),
            ),
        })
    if _steps:
        result = {'propose_steps': _steps, 'continue': True}
    else:
        result = _notice('Open-Meteo does not know %s.' % ', '.join(_places))
elif not _places:
    result = _notice('The company has no city. Name a place, e.g. /forecast place=Paris.')
else:
    _lang = str(user_lang or 'en_US').split('_')[0].lower()
    result = {
        'propose_steps': [
            {
                'op': 'fetch_url',
                'name': _p,
                'url': (
                    'https://geocoding-api.open-meteo.com/v1/search'
                    '?name=%s&count=10&language=%s&format=json'
                ) % (_urlq(_split_place(_p)[0]), _lang),
            }
            for _p in _places
        ],
        'continue': True,
    }
