# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
# SKILL: forecast — Open-Meteo, any city, multi-day.
#
# AUTOCONTENIDO: toda la logica meteorologica vive AQUI, no en el motor. El
# motor (ai engine) solo aporta el mecanismo generico multi-ronda: ejecuta los
# `propose_steps` (fetch_url auto-confirmables) y, si el skill puso `continue`,
# vuelve a ejecutar este code_body con los resultados en `previous_result`.
#
# Rondas (se distinguen mirando `previous_result`):
#   1. previous_result vacio        -> geocodificar las ciudades (fetch geocoding-api).
#   2. previous_result = geocodings -> armar 1 forecast por ciudad con &city=<nombre>.
#   3. previous_result = forecasts  -> parsear y presentar (groups/data + footer).
import json
import re
from datetime import date, datetime, timedelta

result = {}

# --- Constantes de presentacion -------------------------------------------
_WMO = {
    0: ('Despejado', '\u2600\ufe0f'), 1: ('Mayormente despejado', '\U0001f324\ufe0f'),
    2: ('Parcialmente nublado', '\u26c5'), 3: ('Nublado', '\u2601\ufe0f'),
    45: ('Niebla', '\U0001f32b\ufe0f'), 48: ('Niebla', '\U0001f32b\ufe0f'),
    51: ('Llovizna', '\U0001f326\ufe0f'), 53: ('Llovizna', '\U0001f326\ufe0f'),
    55: ('Llovizna', '\U0001f326\ufe0f'), 61: ('Lluvia', '\U0001f327\ufe0f'),
    63: ('Lluvia', '\U0001f327\ufe0f'), 65: ('Lluvia', '\U0001f327\ufe0f'),
    71: ('Nieve', '\u2744\ufe0f'), 73: ('Nieve', '\u2744\ufe0f'),
    75: ('Nieve', '\u2744\ufe0f'), 80: ('Chubascos', '\U0001f326\ufe0f'),
    81: ('Chubascos', '\U0001f326\ufe0f'), 82: ('Chubascos', '\U0001f326\ufe0f'),
    95: ('Tormenta', '\u26c8\ufe0f'), 96: ('Tormenta', '\u26c8\ufe0f'),
    99: ('Tormenta', '\u26c8\ufe0f'),
}
_DOW_EN = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')
_MONTHS = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
    'julio': 7, 'agosto': 8, 'septiembre': 9, 'setiembre': 9,
    'octubre': 10, 'noviembre': 11, 'diciembre': 12,
}
_DAILY_FIELDS = (
    'temperature_2m_max,temperature_2m_min,precipitation_sum,'
    'windspeed_10m_max,winddirection_10m_dominant,uv_index_max,'
    'weathercode,sunrise,sunset'
)
_GEO_HOST = 'geocoding-api.open-meteo.com'
_FC_HOST = 'api.open-meteo.com/v1/forecast'
_URL_SAFE = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~'
_TRAIL = ('para', 'de', 'del', 'en', 'el', 'la', 'los', 'las', 'the', 'for', 'in')


# --- Helpers URL (sin urllib) ---------------------------------------------
def _urlq(text):
    out = []
    for ch in (text or ''):
        if ch in _URL_SAFE:
            out.append(ch)
        else:
            out.append(''.join('%%%02X' % b for b in ch.encode('utf-8')))
    return ''.join(out)


def _unquote(text):
    s = str(text or '').replace('+', ' ')
    buf = bytearray()
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == '%' and i + 2 < n + 1 and i + 3 <= n:
            try:
                buf.append(int(s[i + 1:i + 3], 16))
                i += 3
                continue
            except ValueError:
                pass
        buf.extend(c.encode('utf-8'))
        i += 1
    return buf.decode('utf-8', 'replace')


def _city_from_url(url):
    m = re.search(r'[?&]city=([^&]+)', str(url or ''), re.I)
    return _unquote(m.group(1)).strip() if m else None


# --- Parseo de peticion (ciudades + fecha) ---------------------------------
def _split_cities(text):
    if not text:
        return []
    t = re.sub(r'(?i)\s+\b(?:y|e|and)\b\s+', '|', str(text).strip())
    out = []
    for p in re.split(r'[|,;]+', t):
        p = p.strip()
        p = re.sub(r'(?i)^(?:en|de|del|para|in|for|the)\s+', '', p)
        p = re.sub(r'(?i)\s+(?:para|hoy|ma\u00f1ana|manana|today|tomorrow)$', '', p)
        p = p.strip(' ,.;')
        if p:
            out.append(p)
    return out


def _lugar_fecha(text):
    """'barcelona, roma manana' -> ('barcelona, roma', 'manana')."""
    text = (text or '').strip()
    if not text:
        return None, None
    date_pat = (
        r'(?i)\b('
        r'ma\u00f1ana|manana|hoy|pasado\s+ma\u00f1ana|pasado\s+manana|'
        r'pr\u00f3ximos?\s+\d+\s+d[i\u00ed]as|proximos?\s+\d+\s+dias|'
        r'\d{1,2}\s+de\s+\w+|\d{4}-\d{2}-\d{2}|'
        r'\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)\b'
    )
    m = re.search(date_pat, text)
    if m:
        return (text[:m.start()].strip(' ,;') or None,
                text[m.start():].strip() or None)
    return text, None


def _parse_fecha_range(fecha_text, today):
    """(start_date, end_date, forecast_days, single_date|None)."""
    start, end = today + timedelta(days=1), today + timedelta(days=7)
    if not fecha_text:
        return start, end, 7, None
    t = str(fecha_text).strip().lower()
    if t == 'hoy':
        return today, today, 1, str(today)
    if t in ('ma\u00f1ana', 'manana'):
        d = today + timedelta(days=1)
        return d, d, 1, str(d)
    if t in ('pasado ma\u00f1ana', 'pasado manana'):
        d = today + timedelta(days=2)
        return d, d, 1, str(d)
    m = re.search(r'pr[o\u00f3]ximos?\s+(\d+)\s+d[i\u00ed]as', t)
    if m:
        n = max(1, min(16, int(m.group(1))))
        return today + timedelta(days=1), today + timedelta(days=n), n, None
    m = re.search(r'(\d{1,2})\s+de\s+([a-z\u00e1\u00e9\u00ed\u00f3\u00fa]+)', t)
    if m:
        mon = _MONTHS.get(m.group(2).lower())
        if mon:
            try:
                d = date(today.year, mon, int(m.group(1)))
            except ValueError:
                d = None
            if d and d < today:
                try:
                    d = date(today.year + 1, mon, int(m.group(1)))
                except ValueError:
                    d = None
            if d:
                fd = max(1, min(16, max(0, (d - today).days) + 1))
                return d, d, fd, str(d)
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', t)
    if m:
        try:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            fd = max(1, min(16, max(0, (d - today).days) + 1))
            return d, d, fd, str(d)
        except ValueError:
            pass
    return start, end, 7, None


def _clean_city(raw):
    """'toledo (espana)' -> ('toledo', 'espana'); limpia rellenos finales."""
    s = str(raw or '').strip()
    hint = None
    m = re.search(r'\(([^)]*)\)', s)
    if m:
        hint = (m.group(1).strip() or None)
        s = (s[:m.start()] + ' ' + s[m.end():]).strip()
    s = re.sub(r'\s+', ' ', s)
    changed = True
    while changed and s:
        changed = False
        for f in _TRAIL:
            m2 = re.search(r'(?i)\s+' + re.escape(f) + r'$', s)
            if m2:
                s = s[:m2.start()].rstrip()
                changed = True
    return s.strip(' ,.;'), hint


def _pick_geocode(results, hint):
    if not results:
        return None
    if hint:
        # Normalización inline (evita un def extra: el sandbox limita a 16).
        h = re.sub(r'[^a-z0-9 ]', '', str(hint or '').strip().lower())
        if h:
            for r in results:
                for key in ('country', 'country_code', 'admin1', 'admin2'):
                    rv = re.sub(
                        r'[^a-z0-9 ]', '',
                        str(r.get(key) or '').strip().lower(),
                    )
                    if rv and (h in rv or rv in h):
                        return r
    return results[0]


# --- Helpers de tabla ------------------------------------------------------
def _cielo(code):
    try:
        label, emoji = _WMO.get(int(code), ('Variable', '\U0001f321\ufe0f'))
    except (TypeError, ValueError):
        return '\u2601\ufe0f Nublado'
    return '%s %s' % (emoji, label)


def _fmt_day(iso_date):
    try:
        d = datetime.strptime(str(iso_date)[:10], '%Y-%m-%d')
        return '%s %s' % (_DOW_EN[d.weekday()], d.strftime('%d/%m'))
    except Exception:
        return str(iso_date)


def _fmt_hm(iso_dt):
    s = str(iso_dt or '')
    if 'T' in s:
        return s.split('T', 1)[1][:5]
    return s[:5]


def _num(val, suffix=''):
    if val is None:
        return ''
    try:
        text = '%g' % float(val)
        return text + suffix if suffix else text
    except (TypeError, ValueError):
        return str(val)


def _rows_from_daily(daily, single_date=None):
    if not isinstance(daily, dict):
        return []
    times = daily.get('time') or []
    codes = daily.get('weathercode') or daily.get('weather_code') or []
    tmax = daily.get('temperature_2m_max') or []
    tmin = daily.get('temperature_2m_min') or []
    precip = daily.get('precipitation_sum') or []
    wind = daily.get('windspeed_10m_max') or daily.get('wind_speed_10m_max') or []
    uv = daily.get('uv_index_max') or []
    rise = daily.get('sunrise') or []
    sett = daily.get('sunset') or []
    rows = []
    for i, day in enumerate(times):
        if single_date and str(day)[:10] != str(single_date)[:10]:
            continue
        rows.append({
            'Date': _fmt_day(day),
            'Sky': _cielo(codes[i] if i < len(codes) else None),
            'Max': _num(tmax[i] if i < len(tmax) else None, '\u00b0'),
            'Min': _num(tmin[i] if i < len(tmin) else None, '\u00b0'),
            'Precip mm': _num(precip[i] if i < len(precip) else None),
            'Wind km/h': _num(wind[i] if i < len(wind) else None),
            'UV': _num(uv[i] if i < len(uv) else None),
            'Sunrise': _fmt_hm(rise[i] if i < len(rise) else None),
            'Sunset': _fmt_hm(sett[i] if i < len(sett) else None),
        })
    return rows


def _to_temp(val):
    m = re.search(r'-?\d+(?:\.\d+)?', str(val or '').replace(',', '.'))
    return float(m.group(0)) if m else None


def _footer(city_rows):
    """Comparativa determinista entre ciudades/dias (sin alucinacion)."""
    flat = []
    for city, rows in city_rows:
        for r in rows:
            flat.append((city, r))
    if len(flat) < 2:
        return ''
    multi_city = len(city_rows) > 1
    # Etiqueta inline (ciudad si hay varias, si no la fecha): evita un def
    # anidado extra (el sandbox cuenta también los def internos; tope 16).
    lines = ['Comparison:']
    hot = [(_to_temp(r.get('Max')),
            (c if multi_city else r.get('Date') or '?'), r.get('Max'))
           for c, r in flat if _to_temp(r.get('Max')) is not None]
    if hot:
        b = max(hot, key=lambda t: t[0])
        lines.append('Warmest: %s (%s)' % (b[1], b[2]))
    cold = [(_to_temp(r.get('Min')),
             (c if multi_city else r.get('Date') or '?'), r.get('Min'))
            for c, r in flat if _to_temp(r.get('Min')) is not None]
    if cold:
        b = min(cold, key=lambda t: t[0])
        lines.append('Coolest: %s (min %s)' % (b[1], b[2]))
    windy = [(_to_temp(r.get('Wind km/h')),
              (c if multi_city else r.get('Date') or '?'), r.get('Wind km/h'))
             for c, r in flat if _to_temp(r.get('Wind km/h')) is not None]
    if windy:
        b = max(windy, key=lambda t: t[0])
        lines.append('Windiest: %s (%s km/h)' % (b[1], b[2]))
    return '\n'.join(lines) if len(lines) > 1 else ''


def _bodies(prev, host):
    """Items de previous_result cuya url contiene `host` -> (item, body dict)."""
    out = []
    for it in (prev or []):
        if not isinstance(it, dict):
            continue
        if host not in str(it.get('url') or ''):
            continue
        body = it.get('body')
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except (TypeError, ValueError):
                body = None
        out.append((it, body if isinstance(body, dict) else None))
    return out


# --- Resolver ciudades + fecha de la peticion ------------------------------
try:
    _norm_cities = cities  # inyectado por el normalizador de params (opt-in)
except NameError:
    _norm_cities = None
try:
    _norm_fecha = fecha
except NameError:
    _norm_fecha = None
try:
    _raw = arguments
except NameError:
    _raw = None
try:
    _lugar = lugar
except NameError:
    _lugar = None

_PLACEHOLDER = frozenset({'', 'none', 'null', 'default', 'n/a', 'na'})

def _blank(val):
    if val is None:
        return True
    return str(val).strip().lower() in _PLACEHOLDER

_cities = []
if isinstance(_norm_cities, (list, tuple)) and _norm_cities:
    _cities = [
        str(c).strip() for c in _norm_cities
        if str(c).strip() and str(c).strip().lower() not in _PLACEHOLDER
    ]
    _fecha = None if _blank(_norm_fecha) else _norm_fecha
if not _cities:
    _place, _date_txt = _lugar_fecha('' if _blank(_raw) else _raw)
    if not _place:
        _place, _extra = _lugar_fecha('' if _blank(_lugar) else _lugar)
        if _extra and not _date_txt:
            _date_txt = _extra
    _fecha = None if _blank(_norm_fecha) else _norm_fecha
    if _fecha is None:
        _fecha = None if _blank(_date_txt) else _date_txt
    if not _place:
        _co_city = ''
        _co_state = ''
        try:
            _co_city = (company.city or '').strip()
            _co_state = (
                company.state_id.name if company.state_id else ''
            ) or ''
        except NameError:
            _co_city = ''
            _co_state = ''
        _place = _co_city or _co_state or None
    if _place:
        _cities = _split_cities(_place) or [_place.strip()]

_today = date.today()
_start, _end, _fdays, _single = _parse_fecha_range(_fecha, _today)

# --- Despacho por ronda ----------------------------------------------------
try:
    _prev = previous_result
except NameError:
    _prev = None

_geo = _bodies(_prev, _GEO_HOST)
_fc = _bodies(_prev, _FC_HOST)

if _fc:
    # RONDA 3: presentar. El nombre de ciudad viaja en &city= de cada forecast.
    city_rows = []
    for it, body in _fc:
        if not body or not body.get('daily'):
            continue
        city = _city_from_url(it.get('url')) or 'Location'
        rows = _rows_from_daily(body.get('daily') or {}, single_date=_single)
        if not rows and _single:
            rows = _rows_from_daily(body.get('daily') or {}, single_date=None)
        city_rows.append((city, rows))
    if not city_rows:
        # Renderizable siempre (formatted_text), nunca data vacia: evita que el
        # fast-path degrade por 'presentation_no_html'.
        result = {
            'formatted_text': (
                'Could not parse the Open-Meteo response for %s.'
                % (', '.join(_cities) or 'the requested location')
            ),
            '__return_direct__': True,
        }
    else:
        n_cities = len(city_rows)
        n_days = max((len(r) for _, r in city_rows), default=0)
        footer = _footer(city_rows)
        if n_cities == 1:
            city, rows = city_rows[0]
            if n_days <= 1 and rows:
                summary = 'Forecast — %s, %s' % (city, rows[0].get('Date') or '')
            else:
                summary = 'Forecast — %s (next %s days)' % (city, n_days)
            result = {'summary': summary.strip(), 'data': rows, 'footer': footer}
        elif n_days <= 1:
            names = ', '.join(c for c, _ in city_rows)
            summary = ('Forecast — %s (%s)' % (names, _fecha)) if _fecha \
                else ('Forecast — %s' % names)
            data = []
            for c, rows in city_rows:
                for r in rows:
                    data.append({'City': c, **r})
            result = {'summary': summary, 'data': data, 'footer': footer}
        else:
            groups = [{'title': c, 'rows': rows} for c, rows in city_rows if rows]
            result = {
                'summary': 'Forecast — %s cities (next %s days)' % (
                    n_cities, n_days),
                'groups': groups,
                'footer': footer,
            }
        result['__return_direct__'] = True

elif _geo:
    # RONDA 2: geocodings resueltos -> 1 forecast por ciudad con &city=<nombre>.
    steps = []
    hints = [(_clean_city(c)[1]) for c in _cities]
    for idx, (it, body) in enumerate(_geo):
        results = (body or {}).get('results') or []
        r0 = _pick_geocode(results, hints[idx] if idx < len(hints) else None)
        if not r0:
            continue
        lat, lon = r0.get('latitude'), r0.get('longitude')
        if lat is None or lon is None:
            continue
        rname = r0.get('name') or (
            _cities[idx] if idx < len(_cities) else 'Location')
        tz = _urlq(r0.get('timezone') or 'auto')
        if _single:
            url = ('https://api.open-meteo.com/v1/forecast'
                   '?latitude=%s&longitude=%s&daily=%s&timezone=%s'
                   '&start_date=%s&end_date=%s&city=%s') % (
                lat, lon, _DAILY_FIELDS, tz, _single, _single, _urlq(rname))
        else:
            url = ('https://api.open-meteo.com/v1/forecast'
                   '?latitude=%s&longitude=%s&daily=%s&timezone=%s'
                   '&forecast_days=%s&city=%s') % (
                lat, lon, _DAILY_FIELDS, tz, _fdays, _urlq(rname))
        steps.append({'op': 'fetch_url', 'url': url, 'name': rname})
    if steps:
        result = {'propose_steps': steps, 'continue': True}
    else:
        result = {
            'formatted_text': (
                'Could not geocode %s. Pass a city name, e.g. `/forecast Madrid`.'
                % (', '.join(_cities) or 'the requested location')
            ),
            '__return_direct__': True,
        }

else:
    # RONDA 1: geocodificar cada ciudad (Open-Meteo geocoding API).
    if not _cities:
        result = {
            'formatted_text': (
                'No company city is set. Pass a place, e.g. `/forecast Madrid`.'
            ),
            '__return_direct__': True,
        }
    else:
        lang = 'es'
        steps = []
        for name in _cities:
            clean, _hint = _clean_city(name)
            steps.append({
                'op': 'fetch_url',
                'url': ('https://geocoding-api.open-meteo.com/v1/search'
                        '?name=%s&count=10&language=%s&format=json') % (
                    _urlq(clean or name), lang),
                'name': name,
            })
        result = {'propose_steps': steps, 'continue': True}
