# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Persist binary downloads linked to a Chatboo session (ir.attachment + chips)."""

import base64
import logging
import re
import uuid
from urllib.parse import quote, unquote, urlencode, urlparse

_logger = logging.getLogger(__name__)

# Machine-readable persist outcomes (Safe Plan / LLM channel).
PERSIST_REASON_NO_SESSION = 'no_session'
PERSIST_REASON_NO_BYTES = 'no_bytes'
PERSIST_REASON_SIZE_LIMIT = 'size_limit'
PERSIST_REASON_CHATBOO_UNAVAILABLE = 'chatboo_unavailable'
PERSIST_REASON_SESSION_NOT_FOUND = 'session_not_found'
PERSIST_REASON_CREATE_FAILED = 'create_failed'

CHATBOO_SESSION_MODEL = 'chatboo.session'
CHATBOO_ASYNC_REQUEST_MODEL = 'chatboo.async.request'
ICP_DOWNLOAD_MAX_BYTES = 'pns_ai_chatboo.download_max_bytes'
DEFAULT_DOWNLOAD_MAX_BYTES = 15 * 1024 * 1024

_TEXTual_MIME_PREFIXES = ('text/',)
_TEXTual_MIME_EXACT = frozenset({
    'application/json',
    'application/ld+json',
    'application/xml',
    'text/xml',
    'application/javascript',
    'application/x-javascript',
    'application/xhtml+xml',
})


def get_download_max_bytes(env):
    try:
        raw = env['ir.config_parameter'].sudo().get_param(
            ICP_DOWNLOAD_MAX_BYTES, DEFAULT_DOWNLOAD_MAX_BYTES,
        )
        return max(0, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_DOWNLOAD_MAX_BYTES


def is_binary_content_type(content_type, content_disposition=None):
    """True when the HTTP response should be stored as a file, not LLM text."""
    cd = (content_disposition or '').lower()
    if 'attachment' in cd:
        return True
    ct = (content_type or '').split(';', 1)[0].strip().lower()
    if not ct:
        return False
    if ct in _TEXTual_MIME_EXACT:
        return False
    if any(ct.startswith(p) for p in _TEXTual_MIME_PREFIXES):
        return False
    if ct.startswith('application/'):
        if ct in (
            'application/pdf',
            'application/zip',
            'application/gzip',
            'application/x-gzip',
            'application/octet-stream',
            'application/msword',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument',
        ) or 'officedocument' in ct or 'opendocument' in ct:
            return True
        if ct.endswith('+json') or ct.endswith('+xml'):
            return False
        return True
    if ct.startswith('image/') or ct.startswith('audio/') or ct.startswith('video/'):
        return True
    return False


def is_inline_preview_file(filename, mimetype=None):
    """SVG drawings open in a tab; everything else should download."""
    name = (filename or '').lower()
    mime = (mimetype or '').split(';', 1)[0].strip().lower()
    return mime == 'image/svg+xml' or name.endswith('.svg')


def safe_content_filename(filename):
    """Path segment for /web/content/<id>/<name> (no slashes, no quotes)."""
    name = (filename or 'download').replace('\\', '_').replace('/', '_')
    name = name.replace('"', '').replace('\r', '').replace('\n', '').strip()
    return (name or 'download')[:180]


def content_download_url(attachment_id, access_token, filename, mimetype=None):
    """Chip URL that keeps the proposed name and forces a file download.

    ``/web/content/<id>`` makes the browser save ``74007.pdf``. Putting the
    chip name in the path and ``download=true`` sets Content-Disposition.
    SVG stays on the inline viewer (open in a tab).
    """
    token = (access_token or '').strip()
    name = safe_content_filename(filename)
    att_id = int(attachment_id)
    if is_inline_preview_file(name, mimetype):
        path = '/pns_ai_mcp/session_file/%s' % att_id
        if token:
            return '%s?access_token=%s' % (path, token)
        return path
    path = '/web/content/%s/%s' % (att_id, quote(name, safe='._-'))
    params = {'download': 'true'}
    if token:
        params['access_token'] = token
    return '%s?%s' % (path, urlencode(params))


def mimetype_from_magic_bytes(raw):
    """Best-effort MIME when Content-Type is missing or wrong."""
    if not raw or len(raw) < 4:
        return None
    if raw[:4] == b'%PDF':
        return 'application/pdf'
    if raw[:2] == b'PK':
        return 'application/zip'
    if raw[:3] == b'\x89PN':
        return 'image/png'
    if raw[:6] in (b'GIF87a', b'GIF89a'):
        return 'image/gif'
    if raw[:2] == b'\xff\xd8':
        return 'image/jpeg'
    return None


def looks_like_binary_bytes(raw):
    """Heuristic when Content-Type is missing/wrong (e.g. OpenAPI download)."""
    if not raw or len(raw) < 4:
        return False
    if mimetype_from_magic_bytes(raw):
        return True
    sample = raw[:512]
    non_text = sum(1 for b in sample if b < 9 or (13 < b < 32) or b > 126)
    return non_text > max(32, int(len(sample) * 0.25))


def filename_from_http(url, content_type=None, content_disposition=None):
    """Best-effort filename from URL headers."""
    cd = content_disposition or ''
    m = re.search(r"filename\*=(?:UTF-8''|utf-8'')([^;\s]+)", cd, re.I)
    if m:
        return unquote(m.group(1)).strip() or 'download'
    m = re.search(r'filename="([^"]+)"', cd, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r'filename=([^;\s]+)', cd, re.I)
    if m:
        return m.group(1).strip().strip('"')
    path = urlparse(url or '').path or ''
    base = (path.rsplit('/', 1)[-1] if path else '') or 'download'
    if '.' not in base and content_type:
        ct = content_type.split(';', 1)[0].strip().lower()
        ext_map = {
            'application/pdf': '.pdf',
            'application/zip': '.zip',
            'image/png': '.png',
            'image/jpeg': '.jpg',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
        }
        for key, ext in ext_map.items():
            if ct.startswith(key):
                base += ext
                break
    return base[:255] or 'download'


_FILE_ID_KEYS = (
    'documentId', 'document_id', 'fileId', 'file_id', 'attachmentId',
    'id', 'uuid',
)
_FILE_ID_ALWAYS_KEYS = frozenset({
    'documentId', 'document_id', 'fileId', 'file_id', 'attachmentId',
})
_FILE_NAME_KEYS = (
    'name', 'filename', 'fileName', 'documentName', 'title',
)
_FILE_NAME_EXT = re.compile(
    r'\.(pdf|docx?|xlsx?|pptx?|odt|ods|odp|png|jpe?g|gif|webp|zip|txt|csv'
    r'|html?|md|svg)\s*$',
    re.IGNORECASE,
)


def _svg_download():
    """``svg_download`` via package import, or sibling file (host tests)."""
    try:
        from . import svg_download as mod
        return mod
    except Exception:
        pass
    try:
        import importlib.util
        from pathlib import Path
        path = Path(__file__).resolve().parent / 'svg_download.py'
        spec = importlib.util.spec_from_file_location(
            '_pns_session_svg_download', path,
        )
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


_SVG_DOWNLOAD = None


def _is_generic_name(name):
    global _SVG_DOWNLOAD
    if _SVG_DOWNLOAD is None:
        _SVG_DOWNLOAD = _svg_download() or False
    if _SVG_DOWNLOAD:
        return _SVG_DOWNLOAD.is_generic_attachment_name(name)
    if not name or not isinstance(name, str):
        return True
    stem = name.rsplit('.', 1)[0].strip().lower()
    return bool(
        re.match(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            stem, re.I,
        )
        or re.match(r'^[0-9a-f]{16,}$', stem, re.I)
    )


def _usable_filename(value):
    if value in (None, '', []):
        return None
    text = str(value).strip()
    if not text or _is_generic_name(text):
        return None
    if '://' in text or text.lower().startswith('http'):
        return None
    return text[:255]


def _filename_from_row(payload):
    """Human filename on a listing row: name keys, or any cell with a file ext."""
    if not isinstance(payload, dict):
        return None
    for key in _FILE_NAME_KEYS:
        name = _usable_filename(payload.get(key))
        if name:
            return name
    for val in payload.values():
        if not isinstance(val, str):
            continue
        text = val.strip()
        if not _FILE_NAME_EXT.search(text):
            continue
        name = _usable_filename(text)
        if name:
            return name
    return None


def _should_index_file_id(key, value):
    if value in (None, '', []):
        return False
    text = str(value).strip()
    if not text:
        return False
    if key in _FILE_ID_ALWAYS_KEYS:
        return True
    global _SVG_DOWNLOAD
    if _SVG_DOWNLOAD is None:
        _is_generic_name('')
    if _SVG_DOWNLOAD:
        return _SVG_DOWNLOAD.is_opaque_attachment_stem(text)
    return bool(
        re.match(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            text, re.I,
        )
        or re.match(r'^[0-9a-f]{16,}$', text, re.I)
    )


def file_labels_from_mapping(payload, store=None, _depth=0):
    """Harvest id → human filename from a JSON object or list of objects."""
    out = store if isinstance(store, dict) else {}
    if _depth > 12:
        return out
    if isinstance(payload, list):
        for item in payload:
            file_labels_from_mapping(item, out, _depth=_depth + 1)
        return out
    if not isinstance(payload, dict):
        return out
    name = _filename_from_row(payload)
    if name:
        for key in _FILE_ID_KEYS:
            rid = payload.get(key)
            if not _should_index_file_id(key, rid):
                continue
            out[str(rid).strip()] = name
    for val in payload.values():
        if isinstance(val, (list, dict)) and val is not payload:
            file_labels_from_mapping(val, out, _depth=_depth + 1)
    return out


def file_labels_from_steps(steps, store=None):
    """Harvest id → filename from successful api_call / fetch_url bodies."""
    import json as _json
    out = store if isinstance(store, dict) else {}
    for step in steps or []:
        if not isinstance(step, dict) or step.get('success') is False:
            continue
        body = step.get('body')
        if isinstance(body, str) and body.strip()[:1] in '{[':
            try:
                body = _json.loads(body)
            except Exception:
                continue
        file_labels_from_mapping(body, out)
        chip = step.get('download_chip')
        if isinstance(chip, dict):
            name = _usable_filename(chip.get('name'))
            if name:
                for key in _FILE_ID_KEYS:
                    rid = chip.get(key)
                    if rid not in (None, '', []):
                        out[str(rid)] = name
    return out


def preferred_download_filename(raw_name, arguments=None, labels=None):
    """Human filename: arguments / prior listing, never an opaque storage key."""
    arguments = arguments if isinstance(arguments, dict) else {}
    labels = labels if isinstance(labels, dict) else {}
    candidates = []
    for key in _FILE_ID_KEYS:
        rid = arguments.get(key)
        if rid not in (None, '', []):
            labeled = _usable_filename(labels.get(str(rid)))
            if labeled:
                candidates.append(labeled)
    for key in _FILE_NAME_KEYS:
        named = _usable_filename(arguments.get(key))
        if named:
            candidates.append(named)
    raw = _usable_filename(raw_name)
    if raw:
        candidates.append(raw)
    if candidates:
        return candidates[0]
    text = str(raw_name or '').strip()
    return text[:255] if text else ''


def _registry_model(env, model_name):
    """Return env[model] when the model is installed, else None (O14-safe)."""
    try:
        registry = env.registry
        if model_name not in registry:
            return None
        return env[model_name]
    except Exception:
        return None


def _attachment_access_token(att):
    """Return a portal access token for a freshly created attachment."""
    gen = getattr(att, 'generate_access_token', None)
    if callable(gen):
        tokens = gen()
        if tokens:
            return tokens[0]
    token = str(uuid.uuid4())
    att.sudo().write({'access_token': token})
    return token


def coalesce_download_chips(*groups):
    """Merge chip lists, first URL (or name) wins. Skips empty groups."""
    seen = set()
    out = []
    for group in groups:
        if not group:
            continue
        for chip in group:
            if not isinstance(chip, dict):
                continue
            key = chip.get('url') or chip.get('name')
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(chip)
    return out


def _run_on_committed_cursor(env, fn):
    """Run ``fn(env2)`` on a short cursor and commit.

    The Chatboo worker keeps the inference TX open until ``_finalize`` opens
    a fresh cursor. Downloads created on the worker cursor are invisible
    there. Without ``registry`` (host tests), ``fn`` runs on ``env``.
    """
    registry = getattr(env, 'registry', None)
    if registry is None:
        return fn(env)
    try:
        from odoo import api
    except ImportError:
        return fn(env)
    uid = env.uid
    ctx = dict(getattr(env, 'context', None) or {})
    try:
        with registry.cursor() as cr:
            env2 = api.Environment(cr, uid, ctx)
            result = fn(env2)
            cr.commit()
            return result
    except Exception:
        _logger.debug(
            'Chatboo: committed cursor fallback to caller env',
            exc_info=True,
        )
        return fn(env)


def persist_chatboo_session_file_detail(env, session_id, raw_bytes, filename,
                                        mimetype=None):
    """Persist download bytes; return {ok, chip?, reason?, ...} for diagnostics."""
    if not session_id:
        _logger.info('Chatboo download skipped: missing session id')
        return {'ok': False, 'reason': PERSIST_REASON_NO_SESSION}
    if not raw_bytes:
        _logger.info('Chatboo download skipped: empty payload (session %s)', session_id)
        return {'ok': False, 'reason': PERSIST_REASON_NO_BYTES, 'session_id': int(session_id)}

    max_bytes = get_download_max_bytes(env)
    size = len(raw_bytes)
    if max_bytes and size > max_bytes:
        _logger.info(
            'Chatboo download skipped: %s bytes > limit %s (session %s)',
            size, max_bytes, session_id,
        )
        return {
            'ok': False,
            'reason': PERSIST_REASON_SIZE_LIMIT,
            'size': size,
            'max_bytes': max_bytes,
            'session_id': int(session_id),
        }

    Session = _registry_model(env, CHATBOO_SESSION_MODEL)
    if Session is None:
        _logger.warning(
            'Chatboo download skipped: model %s not installed (session %s)',
            CHATBOO_SESSION_MODEL, session_id,
        )
        return {
            'ok': False,
            'reason': PERSIST_REASON_CHATBOO_UNAVAILABLE,
            'session_id': int(session_id),
        }

    session = Session.sudo().browse(int(session_id))
    if not session.exists():
        _logger.warning('Chatboo download skipped: session %s not found', session_id)
        return {
            'ok': False,
            'reason': PERSIST_REASON_SESSION_NOT_FOUND,
            'session_id': int(session_id),
        }

    name = (filename or 'download')[:255]
    mimetype = (mimetype or 'application/octet-stream').split(';', 1)[0].strip()
    try:
        from .svg_download import (
            ext_from_name_or_mime,
            is_generic_attachment_name,
            utterance_filename,
        )
        if is_generic_attachment_name(name):
            ctx = getattr(env, 'context', None) or {}
            ext = ext_from_name_or_mime(name, mimetype) or 'bin'
            better = utterance_filename(
                prompt=ctx.get('user_message') or '',
                skill_code=ctx.get('active_skill_code') or '',
                ext=ext,
                fallback='',
            )
            if better and not is_generic_attachment_name(better):
                name = better[:255]
    except Exception:
        pass
    b64 = base64.b64encode(raw_bytes).decode('ascii')
    sid = session.id

    def _create(env2):
        att = env2['ir.attachment'].sudo().create({
            'name': name,
            'datas': b64,
            'mimetype': mimetype,
            'res_model': CHATBOO_SESSION_MODEL,
            'res_id': sid,
        })
        token = _attachment_access_token(att)
        return {
            'ok': True,
            'chip': {
                'name': name,
                'url': content_download_url(att.id, token, name, mimetype),
                'mimetype': mimetype,
                'size': size,
                'source': 'download',
            },
            'session_id': sid,
        }

    try:
        return _run_on_committed_cursor(env, _create)
    except Exception as exc:
        _logger.warning(
            'Chatboo: could not persist session download %s (session %s)',
            name, session_id, exc_info=True,
        )
        return {
            'ok': False,
            'reason': PERSIST_REASON_CREATE_FAILED,
            'session_id': int(session_id),
            'detail': str(exc)[:200],
        }


def persist_chatboo_session_file(env, session_id, raw_bytes, filename,
                                   mimetype=None):
    """Store bytes as ir.attachment on chatboo.session; return download chip."""
    detail = persist_chatboo_session_file_detail(
        env, session_id, raw_bytes, filename, mimetype=mimetype,
    )
    return detail.get('chip') if detail.get('ok') else None


def build_binary_stored_meta(persist_detail, filename, size):
    """LLM-facing JSON metadata after a binary fetch_url / api_call."""
    detail = persist_detail or {}
    chip = detail.get('chip') if detail.get('ok') else None
    reason = detail.get('reason')
    stored_meta = {
        'stored': bool(chip),
        'filename': (chip or {}).get('name') or filename,
        'size': size,
    }
    if chip:
        stored_meta['message'] = (
            'File saved in chat history as a download chip on this assistant message. '
            'Tell the user the file is attached above; one short coherent sentence. '
            'If other APIs returned not-found for a different source, explain where '
            'this file came from without contradicting that it is attached.'
        )
        stored_meta['chip'] = {
            k: chip[k] for k in ('name', 'url', 'mimetype', 'size') if k in chip
        }
        return stored_meta

    messages = {
        PERSIST_REASON_NO_SESSION: (
            'File received but no Chatboo session is active, so it was not saved.'
        ),
        PERSIST_REASON_NO_BYTES: (
            'File response was empty; nothing was saved in chat history.'
        ),
        PERSIST_REASON_SIZE_LIMIT: (
            'File exceeds the configured download limit (pns_ai_chatboo.download_max_bytes).'
        ),
        PERSIST_REASON_CHATBOO_UNAVAILABLE: (
            'Chatboo is not available on this instance; file was not saved in chat history.'
        ),
        PERSIST_REASON_SESSION_NOT_FOUND: (
            'Chatboo session no longer exists; file was not saved in chat history.'
        ),
        PERSIST_REASON_CREATE_FAILED: (
            'File received but attachment creation failed; not saved in chat history.'
        ),
    }
    stored_meta['reason'] = reason or 'unknown'
    stored_meta['message'] = messages.get(
        reason,
        'File received but could not be saved in chat history.',
    )
    if reason == PERSIST_REASON_SIZE_LIMIT:
        stored_meta['max_bytes'] = detail.get('max_bytes')
    if detail.get('detail'):
        stored_meta['detail'] = detail['detail']
    return stored_meta


def collect_download_chips(results):
    """Extract download chips from execute_safe_plan result rows."""
    chips = []
    for item in results or []:
        if not isinstance(item, dict):
            continue
        chip = item.get('download_chip')
        if isinstance(chip, dict) and chip.get('url'):
            chips.append(chip)
    return chips


def chatboo_session_id_from_env(env):
    """Resolve Chatboo session id from env context or operation_data."""
    ctx = env.context or {}
    sid = ctx.get('chatboo_session_id')
    if sid:
        return int(sid)
    return None


def resolve_chatboo_session_id(env):
    """Best-effort session id for download persistence during Safe Plan."""
    sid = chatboo_session_id_from_env(env)
    if sid:
        return sid
    try:
        from odoo.http import request as http_request
        if http_request and getattr(http_request, 'chatboo_options', None):
            sid = http_request.chatboo_options.get('chatboo_session_id')
            if sid:
                return int(sid)
    except Exception:
        pass
    try:
        Job = _registry_model(env, 'chatboo.async.request')
        if Job:
            job = Job.search([
                ('user_id', '=', env.uid),
                ('state', 'in', ('pending', 'running')),
            ], order='id desc', limit=1)
            if job.session_id:
                return job.session_id.id
    except Exception:
        pass
    return None


def _decode_b64_payload(value):
    if not value or not isinstance(value, str):
        return None
    raw = value.strip()
    if raw.startswith('data:') and ';base64,' in raw:
        raw = raw.split(';base64,', 1)[1]
    if len(raw) < 64:
        return None
    try:
        return base64.b64decode(raw, validate=False)
    except Exception:
        return None


def _pick_first(mapping, keys):
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        val = mapping.get(key)
        if val not in (None, '', []):
            return val
    return None


def try_extract_binary_payload(body, tool_name=None, server_code=None,
                               arguments=None):
    """Detect embedded file bytes in MCP/OpenAPI text or JSON bodies."""
    filename = None
    mimetype = None
    raw = None
    arguments = arguments or {}

    if isinstance(body, dict):
        payload = body
    elif isinstance(body, str) and body.strip():
        text = body.strip()
        if text.startswith('{') or text.startswith('['):
            try:
                import json as _json
                payload = _json.loads(text)
            except Exception:
                payload = None
        else:
            payload = None
        if payload is None:
            raw = _decode_b64_payload(text)
    else:
        return None

    if isinstance(payload, dict):
        nested = payload.get('result') or payload.get('data') or payload
        if isinstance(nested, dict) and nested is not payload:
            payload = nested
        for key in (
            'file', 'fileContent', 'content', 'data', 'document',
            'base64', 'bytes', 'body', 'file_data', 'fileData',
            'binary', 'blob',
        ):
            candidate = payload.get(key)
            if isinstance(candidate, str):
                decoded = _decode_b64_payload(candidate)
                if decoded:
                    raw = decoded
                    break
            elif isinstance(candidate, (bytes, bytearray)):
                raw = bytes(candidate)
                break
        filename = _pick_first(payload, (
            'filename', 'fileName', 'name', 'documentName', 'title',
        ))
        if not _usable_filename(filename):
            filename = None
            for key in ('name', 'documentName', 'title', 'fileName', 'filename'):
                filename = _usable_filename(payload.get(key))
                if filename:
                    break
        mimetype = _pick_first(payload, (
            'mimeType', 'mimetype', 'contentType', 'content_type', 'mime',
        ))

    if not raw:
        return None
    if not _usable_filename(filename):
        filename = _usable_filename(
            _pick_first(arguments, ('filename', 'fileName', 'name', 'documentName'))
        )
        if not filename and mimetype:
            filename = filename_from_http('', mimetype, None)
        if not _usable_filename(filename):
            filename = 'download'
    if not mimetype:
        mimetype = 'application/octet-stream'
    return {
        'content': raw,
        'content_type': mimetype,
        'content_disposition': 'attachment; filename="%s"' % filename,
        'filename': filename,
        'url': '%s/%s' % (server_code or 'api', tool_name or 'download'),
    }


def extract_binary_from_mcp_blocks(blocks, tool_name=None, arguments=None):
    """Return a _binary dict from MCP tools/call content blocks."""
    if not blocks:
        return None
    if isinstance(blocks, dict):
        blocks = [blocks]
    if not isinstance(blocks, list):
        return None

    filename = _usable_filename(_pick_first(arguments or {}, (
        'filename', 'fileName', 'name', 'documentName',
    )))
    mimetype = None
    raw = None

    for block in blocks:
        if not isinstance(block, dict):
            continue
        btype = (block.get('type') or '').lower()
        if btype == 'image':
            raw = _decode_b64_payload(block.get('data') or block.get('blob'))
            mimetype = block.get('mimeType') or block.get('mimetype') or 'image/png'
            filename = filename or _usable_filename(block.get('name'))
            break
        if btype == 'resource':
            resource = block.get('resource') or {}
            if isinstance(resource, dict):
                raw = _decode_b64_payload(
                    resource.get('blob') or resource.get('data')
                )
                mimetype = (
                    resource.get('mimeType') or resource.get('mimetype')
                    or mimetype
                )
                filename = filename or _usable_filename(resource.get('name'))
                if raw:
                    break
        if btype == 'text':
            extracted = try_extract_binary_payload(
                block.get('text') or '',
                tool_name=tool_name,
                arguments=arguments,
            )
            if extracted:
                return {
                    '_binary': True,
                    'content': extracted['content'],
                    'content_type': extracted['content_type'],
                    'content_disposition': extracted['content_disposition'],
                    'url': extracted.get('url') or '',
                    'filename': extracted.get('filename'),
                }

    if not raw:
        return None
    filename = preferred_download_filename(filename, arguments=arguments)
    if not _usable_filename(filename):
        if mimetype:
            filename = filename_from_http('', mimetype, None)
        if not _usable_filename(filename):
            filename = 'download'
    if not mimetype:
        mimetype = 'application/octet-stream'
    return {
        '_binary': True,
        'content': raw,
        'content_type': mimetype,
        'content_disposition': 'attachment; filename="%s"' % filename,
        'url': '',
        'filename': filename,
    }


def notify_chatboo_session_files_updated(env, session_id):
    """Ask Chatboo clients to reload session messages (download chips)."""
    if not session_id:
        return
    try:
        session = env['chatboo.session'].browse(int(session_id))
        if not session.exists():
            return
        partner = session.user_id.partner_id
        if not partner:
            return
        payload = {
            'type': 'pns_chatboo_sync',
            'action': 'message_received',
            'session_id': int(session_id),
        }
        bus = env['bus.bus']
        sendone = getattr(bus, '_sendone', None)
        if sendone:
            sendone(partner, 'pns_chatboo_sync', payload)
            return
        import json as _json
        channel = (env.cr.dbname, 'res.partner', partner.id)
        legacy = getattr(bus, 'sendone', None)
        if legacy:
            legacy(channel, _json.dumps(payload, ensure_ascii=False))
    except Exception:
        _logger.debug(
            'Chatboo: could not notify session files update (session %s)',
            session_id, exc_info=True,
        )


def chatboo_session_id_from_operation_data(data):
    if not isinstance(data, dict):
        return None
    sid = data.get('chatboo_session_id')
    if sid:
        return int(sid)
    return None


def _session_turn_in_progress(env, session_id):
    """True while a Chatboo async job is still saving the current turn."""
    Async = _registry_model(env, CHATBOO_ASYNC_REQUEST_MODEL)
    if not Async:
        return False
    return bool(Async.sudo().search([
        ('session_id', '=', int(session_id)),
        ('state', 'in', ('pending', 'running')),
    ], limit=1))


def merge_download_chips_into_session(env, session_id, chips):
    """Append download chips to the last assistant message, or stage them."""
    if not session_id or not chips:
        return
    session_id = int(session_id)
    Session = _registry_model(env, CHATBOO_SESSION_MODEL)
    if not Session:
        return
    session = Session.sudo().browse(session_id)
    if not session.exists():
        return
    if _session_turn_in_progress(env, session_id):
        def _stage(env2):
            sess = env2[CHATBOO_SESSION_MODEL].sudo().browse(session_id)
            if sess.exists() and hasattr(sess, 'stage_assistant_download_chips'):
                sess.stage_assistant_download_chips(chips)
                notify_chatboo_session_files_updated(env2, session_id)
        try:
            _run_on_committed_cursor(env, _stage)
        except Exception:
            _logger.debug(
                'Chatboo: committed stage failed (session %s)',
                session_id, exc_info=True,
            )
            if hasattr(session, 'stage_assistant_download_chips'):
                session.stage_assistant_download_chips(chips)
                notify_chatboo_session_files_updated(env, session_id)
        return
    if hasattr(session, 'apply_assistant_download_chips'):
        session.apply_assistant_download_chips(chips)
        notify_chatboo_session_files_updated(env, session_id)
        return
    messages = session.get_messages()
    if messages and messages[-1].get('role') == 'assistant':
        existing = list(messages[-1].get('files') or [])
        messages[-1]['files'] = existing + list(chips)
        session.set_messages(messages)
        notify_chatboo_session_files_updated(env, session_id)
    elif hasattr(session, 'stage_assistant_download_chips'):
        session.stage_assistant_download_chips(chips)
        notify_chatboo_session_files_updated(env, session_id)
