# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""OpenAI and OpenAI-compatible HTTP chat-completions driver (default)."""

import base64
import io
import json
import logging
import struct
import requests
import uuid
from .base import LLMDriver
from ..utils.timeouts import LLM_HTTP_DEFAULT, LLM_HTTP_RETRY  # noqa: F401 (LLM_HTTP_RETRY available for callers)

_logger = logging.getLogger(__name__)

_TRANSCRIBE_TIMEOUT = 60
_SHAPE_STATUS = (400, 404, 415, 422)


def _audio_format(mime, filename=''):
    kind = (mime or '').split(';', 1)[0].strip().lower()
    known = {
        'audio/webm': 'webm',
        'audio/ogg': 'ogg',
        'audio/mpeg': 'mp3',
        'audio/mp3': 'mp3',
        'audio/mp4': 'm4a',
        'audio/x-m4a': 'm4a',
        'audio/wav': 'wav',
        'audio/x-wav': 'wav',
        'audio/flac': 'flac',
        'audio/aac': 'aac',
    }
    if kind in known:
        return known[kind]
    name = (filename or '').lower()
    for ext in ('webm', 'ogg', 'mp3', 'm4a', 'wav', 'flac', 'aac'):
        if name.endswith('.' + ext):
            return ext
    return 'webm'


def _spoken_text(body):
    """Text from a chat reply. Empty if none."""
    if not isinstance(body, dict):
        return ''
    raw = body.get('text')
    if isinstance(raw, str) and raw.strip():
        return raw
    choices = body.get('choices')
    if not isinstance(choices, list) or not choices:
        return ''
    first = choices[0] if isinstance(choices[0], dict) else {}
    msg = first.get('message') if isinstance(first.get('message'), dict) else {}
    content = msg.get('content')
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get('text'), str):
                parts.append(item['text'])
        return ''.join(parts)
    return ''


def _with_text(body):
    if not isinstance(body, dict):
        return body
    said = _spoken_text(body)
    if said and body.get('text') != said:
        body = dict(body, text=said)
    return body


# The verb probe is answered by the HTTP shape, not by the clip. The clip
# still has to be one a transcriber accepts: OpenAI-style endpoints reject
# anything under 0.1 s with a 400, which would read as "no speech API".
_PROBE_SECONDS = 1

# The chat verb hears audio as a question unless told to write it down.
_TRANSCRIBE_INSTRUCTION = (
    'Transcribe the speech in this audio word for word, in the language '
    'spoken. Reply with the transcript only: no answer, no commentary, no '
    'formatting. If there is no speech, reply with an empty message.'
)
_VOCABULARY_LEAD = 'Words likely to appear: '


def _silent_wav():
    """One second of PCM silence for the speech probe. Not a model name."""
    data = b'\x00\x00' * (8000 * _PROBE_SECONDS)
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + len(data), b'WAVE', b'fmt ', 16,
        1, 1, 8000, 16000, 2, 16, b'data', len(data),
    )
    return header + data


def _http_error_message(resp):
    err_msg = resp.text or ('HTTP %s' % resp.status_code)
    try:
        err_body = resp.json()
    except Exception:
        return err_msg
    if not isinstance(err_body, dict):
        return err_msg
    err = err_body.get('error', err_body)
    if isinstance(err, dict):
        return err.get('message') or err_msg
    if isinstance(err, str) and err:
        return err
    return err_msg

class OpenAIDriver(LLMDriver):
    """Driver for OpenAI and all OpenAI-compatible HTTP APIs.

    This is the *default* driver and covers the majority of providers:

    ========================  ==============================================
    Provider                  Endpoint shape
    ========================  ==============================================
    OpenAI (native)           ``https://api.openai.com/v1/chat/completions``
    Azure OpenAI              ``https://<resource>.openai.azure.com/openai/deployments/<model>/chat/completions``
    Ollama (local)            ``http://localhost:11434/v1/chat/completions``
    LMStudio (local)          ``http://localhost:1234/v1/chat/completions``
    Lemonade (local)          ``http://localhost:13305/api/v1/chat/completions``
    vLLM                      ``http://<host>:8000/v1/chat/completions``
    Groq                      ``https://api.groq.com/openai/v1/chat/completions``
    Google Gemini (compat)    ``https://generativelanguage.googleapis.com/v1beta/openai/chat/completions``
    AI Router (PNS)           ``https://<host>/api/v1/chat/completions``
    ========================  ==============================================

    Authentication
    --------------
    All OpenAI-compatible providers use ``Authorization: Bearer <api_key>``.
    The key comes from ``config['api_key']`` during ``initialize()``.

    Model listing
    -------------
    The ``ai.provider`` Odoo model derives the models URL from the chat
    endpoint by replacing ``/chat/completions`` with ``/models``::

        POST https://api.openai.com/v1/chat/completions  →  chat
        GET  https://api.openai.com/v1/models             →  model list

    Response: ``{"data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}, ...]}``

    Tool calling
    ------------
    Tools are sent as ``"tools": [...]`` in the request payload.
    **Important**: some gateways (vLLM, OVH) return HTTP 422 if ``tools``
    is present but ``tool_choice`` is absent. This driver always sends
    ``"tool_choice": "auto"`` when tools are provided.

    Temperature
    -----------
    Always sent. All OpenAI-compatible APIs accept the ``temperature``
    parameter (unlike Anthropic which may reject it for certain models).

    Error handling
    --------------
    Error payloads vary wildly across gateways:

    - OpenAI/vLLM: ``{"error": {"code": "..", "message": "..", "type": ".."}}``
    - nginx/local: ``{"error": "Unauthorized. Bearer token required."}``
    - bare string: ``"some error"``

    The driver normalizes all shapes before raising ``RuntimeError``, so
    the orchestrator always gets a clean error message.
    """
    
    def __init__(self):
        super().__init__()
        self.endpoint = ""
        self.protocol = "openai"
        self.api_key = ""
        self.temperature = 0.7
        self.extra_headers = {}

    def initialize(self, config):
        # The base.py LLMDriver requires us to implement this if it was abstract, though base initialize is often just `pass`. 
        # We handle config here.
        # super().initialize(config) # base initialize is abstract but empty usually, let's not call it just in case
        self.protocol = config.get("protocol", "openai")
        self.endpoint = config.get("endpoint", "")
        self.api_key = config.get("api_key", "")
        self.temperature = float(config.get("temperature", 0.7))
        self.extra_headers = config.get("extra_headers", {})
        self._model_name_internal = (config.get("model_name") or "").strip()
        self.stt_support = (config.get("stt_support") or "unknown").strip() or "unknown"
        self.context_window = int(config.get("context_window", 16384))

    @property
    def driver_name(self) -> str:
        return "OpenAIDriver"

    @property
    def model_name(self) -> str:
        return getattr(self, '_model_name_internal', '')


    def is_loaded(self) -> bool:
        return True

    def format_messages(self, messages, tools=None) -> str:
        # Not used natively since we override chat_completion
        return ""

    def generate(self, prompt, max_tokens=None, temperature=0.0, stop=None):
        # Not used natively since we override chat_completion
        return {}

    def parse_response(self, raw_response):
        # Not used natively since we override chat_completion
        return raw_response

    def chat_completion(self, messages, tools=None, **kwargs):
        temp = kwargs.get('temperature', self.temperature)
        tool_choice = kwargs.get('tool_choice')
        timeout = kwargs.get('timeout', LLM_HTTP_DEFAULT)
        return self._openai_chat(
            messages, tools,
            temperature=temp, tool_choice=tool_choice, timeout=timeout,
            max_tokens=kwargs.get('max_tokens'),
            json_mode=bool(kwargs.get('json_mode')),
            images=kwargs.get('images'),
            disable_thinking=bool(kwargs.get('disable_thinking')),
        )

    @staticmethod
    def _coalesce_system(messages):
        """One leading system message. Some servers reject a later system."""
        system_parts = []
        rest = []
        for msg in messages or []:
            if msg.get('role') == 'system':
                content = msg.get('content') or ''
                if content:
                    system_parts.append(content)
            else:
                rest.append(msg)
        if not system_parts:
            return list(messages or [])
        return [{'role': 'system', 'content': '\n\n'.join(system_parts)}] + rest

    def _with_images(self, messages, images):
        """Attach images to the last user message as image_url parts."""
        shots = [img for img in (images or []) if img]
        msgs = [dict(m) for m in (messages or [])]
        if not shots:
            return self._coalesce_system(msgs)
        parts = []
        idx = None
        for i in range(len(msgs) - 1, -1, -1):
            if msgs[i].get('role') == 'user':
                idx = i
                break
        if idx is None:
            msgs.append({'role': 'user', 'content': ''})
            idx = len(msgs) - 1
        content = msgs[idx].get('content') or ''
        if isinstance(content, str):
            if content:
                parts.append({'type': 'text', 'text': content})
        elif isinstance(content, list):
            parts.extend(content)
        for img in shots:
            url = img if str(img).startswith('data:') else (
                'data:image/png;base64,%s' % img
            )
            parts.append({'type': 'image_url', 'image_url': {'url': url}})
        msgs[idx] = dict(msgs[idx], content=parts)
        return self._coalesce_system(msgs)

    def _stt_model(self):
        """The model on this provider. Nothing else is substituted."""
        return (self.model_name or '').strip()

    @staticmethod
    def transcriptions_url(endpoint):
        """Sibling file-upload address derived from this driver's chat URL."""
        base = (endpoint or '').strip().rstrip('/')
        if not base:
            return ''
        for path in (
            '/api/v1/chat/completions',
            '/v1/chat/completions',
            '/chat/completions',
        ):
            if path in base:
                root = base.split(path)[0].rstrip('/')
                if path.startswith('/api/v1'):
                    return root + '/api/v1/audio/transcriptions'
                return root + '/v1/audio/transcriptions'
        if base.endswith('/api/v1'):
            return base + '/audio/transcriptions'
        if base.endswith('/v1'):
            return base + '/audio/transcriptions'
        return ''

    def _transcribe_chat(self, audio, filename='', mime='', prompt='', timeout=None):
        model = self._stt_model()
        url = (self.endpoint or '').strip()
        if not url or not audio or not model:
            return {'error': 'no_transcribe'}
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = 'Bearer %s' % self.api_key
        text = _TRANSCRIBE_INSTRUCTION
        hint = (prompt or '').strip()
        if hint:
            text = '%s\n%s%s' % (text, _VOCABULARY_LEAD, hint)
        parts = [{'type': 'text', 'text': text}]
        parts.append({
            'type': 'input_audio',
            'input_audio': {
                'data': base64.b64encode(audio).decode('ascii'),
                'format': _audio_format(mime, filename),
            },
        })
        payload = {
            'model': model,
            'messages': [{'role': 'user', 'content': parts}],
            'temperature': 0,
            'modalities': ['text'],
        }
        try:
            resp = requests.post(
                url, headers=headers, json=payload,
                timeout=timeout or _TRANSCRIBE_TIMEOUT,
            )
        except Exception as exc:
            _logger.exception('OpenAI chat transcription failed')
            return {'error': str(exc) or 'network'}
        if resp.status_code != 200:
            out = {'error': _http_error_message(resp)}
            if resp.status_code in _SHAPE_STATUS:
                out['shape_rejected'] = True
            return out
        try:
            body = resp.json()
        except Exception:
            return {'error': 'bad_stt_payload'}
        if not isinstance(body, dict):
            return {'error': 'bad_stt_payload'}
        return {'body': _with_text(body), 'stt': 'chat'}

    def _transcribe_file(self, audio, filename='', mime='', language='', prompt='', timeout=None):
        url = self.transcriptions_url(self.endpoint)
        model = self._stt_model()
        if not url or not audio or not model:
            return {'error': 'no_transcribe'}
        payload = {
            'model': model,
            'temperature': '0',
            'response_format': 'json',
        }
        lang = (language or '').strip().replace('_', '-').split('-', 1)[0].lower()
        if lang:
            payload['language'] = lang
        hint = (prompt or '').strip()
        if hint:
            payload['prompt'] = hint
        headers = {}
        if self.api_key:
            headers['Authorization'] = 'Bearer %s' % self.api_key
        files = {
            'file': (
                filename or 'audio.webm',
                io.BytesIO(audio),
                mime or 'application/octet-stream',
            ),
        }
        try:
            resp = requests.post(
                url, headers=headers, data=payload, files=files,
                timeout=timeout or _TRANSCRIBE_TIMEOUT,
            )
        except Exception as exc:
            _logger.exception('OpenAI file transcription failed')
            return {'error': str(exc) or 'network'}
        if resp.status_code != 200:
            out = {'error': _http_error_message(resp)}
            if resp.status_code in _SHAPE_STATUS:
                out['shape_rejected'] = True
            return out
        try:
            body = resp.json()
        except Exception:
            return {'error': 'bad_stt_payload'}
        if not isinstance(body, dict):
            return {'error': 'bad_stt_payload'}
        return {'body': _with_text(body), 'stt': 'transcriptions'}

    def transcribe(self, audio, filename='', mime='', language='', prompt=''):
        """Use the probed speech verb. Unknown tries chat, then file upload."""
        shape = (self.stt_support or 'unknown').strip() or 'unknown'
        if shape == 'no':
            return {'error': 'no_transcribe'}
        if shape == 'transcriptions':
            return self._transcribe_file(
                audio, filename=filename, mime=mime,
                language=language, prompt=prompt,
            )
        if shape == 'chat':
            return self._transcribe_chat(
                audio, filename=filename, mime=mime, prompt=prompt,
            )
        heard = self._transcribe_chat(
            audio, filename=filename, mime=mime, prompt=prompt,
        )
        if heard.get('body'):
            return heard
        file_heard = self._transcribe_file(
            audio, filename=filename, mime=mime,
            language=language, prompt=prompt,
        )
        if file_heard.get('body'):
            return file_heard
        return heard

    def probe_stt(self, timeout=15):
        """Which speech verb this model answers: chat, transcriptions, or no.

        Sends a silent clip. Does not inspect the model name.
        Raises RuntimeError on auth/network so the caller can keep 'unknown'.
        """
        clip = _silent_wav()
        chat = self._transcribe_chat(
            clip, filename='probe.wav', mime='audio/wav', timeout=timeout,
        )
        if chat.get('body'):
            return 'chat'
        if chat.get('error') and not chat.get('shape_rejected') and chat.get('error') != 'no_transcribe':
            raise RuntimeError(chat.get('error'))
        uploaded = self._transcribe_file(
            clip, filename='probe.wav', mime='audio/wav', timeout=timeout,
        )
        if uploaded.get('body'):
            return 'transcriptions'
        if uploaded.get('error') and not uploaded.get('shape_rejected') and uploaded.get('error') != 'no_transcribe':
            raise RuntimeError(uploaded.get('error'))
        return 'no'

    def _openai_chat(
        self, messages, tools, temperature=None, tool_choice=None,
        timeout=LLM_HTTP_DEFAULT, max_tokens=None, json_mode=False,
        images=None, disable_thinking=False,
    ):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        headers.update(self.extra_headers)
        
        # Ensure we don't have None values in headers
        headers = {k: v for k, v in headers.items() if v is not None}
        
        payload = {
            "model": self.model_name,
            "messages": self._with_images(messages, images),
            "temperature": temperature if temperature is not None else self.temperature,
        }
        if max_tokens:
            payload["max_tokens"] = int(max_tokens)
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if disable_thinking:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        if tools:
            payload["tools"] = tools
            # Always set tool_choice when tools are present.
            # OVH/vLLM returns 422 if tools are sent without explicit tool_choice.
            if tool_choice:
                payload["tool_choice"] = tool_choice
            else:
                payload["tool_choice"] = "auto"

        _logger.info("OpenAIDriver request to %s model %s", self.endpoint, self.model_name)
        response = requests.post(
            self.endpoint, headers=headers, json=payload, timeout=timeout,
        )
        
        if response.status_code != 200:
            err_body = None
            try:
                err_body = response.json()
            except Exception:
                err_body = None

            # The error payload is wildly inconsistent across gateways:
            #  - OpenAI/vLLM:  {"error": {"code": .., "message": .., "type": ..}}
            #  - nginx/local:  {"error": "Unauthorized. Bearer token required."}
            #  - bare string:  "some error"
            # Normalise all shapes so we never crash parsing the very message
            # that explains why the call failed (this used to surface the
            # useless "'str' object has no attribute 'get'").
            err_code = ""
            err_type = ""
            err_msg = response.text
            if isinstance(err_body, dict):
                err = err_body.get("error", err_body)
                if isinstance(err, dict):
                    err_code = err.get("code", "") or ""
                    err_type = err.get("type", "") or ""
                    err_msg = err.get("message") or response.text
                elif isinstance(err, str):
                    err_msg = err or response.text
            elif isinstance(err_body, str):
                err_msg = err_body or response.text

            # Diagnóstico específico: modelo inválido o deprecado
            if response.status_code == 400 and (
                err_code in ("model_not_found", "invalid_model")
                or "does not exist" in err_msg
                or "deprecated" in err_msg.lower()
                or (err_type == "invalid_request_error" and self.model_name in err_msg)
            ):
                raise RuntimeError(
                    f"Modelo '{self.model_name}' no válido o deprecado en OpenAI. "
                    f"Actualiza la configuración del proveedor en Odoo (Settings → AI Providers). "
                    f"Detalle: {err_msg}"
                )

            _logger.error(
                "OpenAIDriver HTTP %s from %s (model %s): %s",
                response.status_code, self.endpoint, self.model_name, err_msg,
            )
            raise RuntimeError(
                "HTTP %s from %s: %s" % (response.status_code, self.endpoint, err_msg)
            )

        return response.json()

    def _raise_http(self, response):
        err_body = None
        try:
            err_body = response.json()
        except Exception:
            err_body = None
        err_code = ''
        err_type = ''
        err_msg = response.text
        if isinstance(err_body, dict):
            err = err_body.get('error', err_body)
            if isinstance(err, dict):
                err_code = err.get('code', '') or ''
                err_type = err.get('type', '') or ''
                err_msg = err.get('message') or response.text
            elif isinstance(err, str):
                err_msg = err or response.text
        elif isinstance(err_body, str):
            err_msg = err_body or response.text
        if response.status_code == 400 and (
            err_code in ('model_not_found', 'invalid_model')
            or 'does not exist' in err_msg
            or 'deprecated' in err_msg.lower()
            or (err_type == 'invalid_request_error' and self.model_name in err_msg)
        ):
            raise RuntimeError(
                "Modelo '%s' no válido o deprecado en OpenAI. "
                'Actualiza la configuración del proveedor en Odoo '
                '(Settings → AI Providers). Detalle: %s' % (self.model_name, err_msg)
            )
        raise RuntimeError(
            'HTTP %s from %s: %s' % (response.status_code, self.endpoint, err_msg)
        )

    def iter_chat(self, messages, tools=None, **kwargs):
        """Yield each text piece, then the finished message."""
        temp = kwargs.get('temperature', self.temperature)
        timeout = kwargs.get('timeout', LLM_HTTP_DEFAULT)
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % self.api_key,
        }
        headers.update(self.extra_headers or {})
        headers = {k: v for k, v in headers.items() if v is not None}
        payload = {
            'model': self.model_name,
            'messages': self._with_images(messages, kwargs.get('images')),
            'temperature': temp if temp is not None else self.temperature,
            'stream': True,
            'stream_options': {'include_usage': True},
        }
        max_tokens = kwargs.get('max_tokens')
        if max_tokens:
            payload['max_tokens'] = int(max_tokens)
        if kwargs.get('json_mode'):
            payload['response_format'] = {'type': 'json_object'}
        if kwargs.get('disable_thinking'):
            payload['chat_template_kwargs'] = {'enable_thinking': False}
        if tools:
            payload['tools'] = tools
            payload['tool_choice'] = kwargs.get('tool_choice') or 'auto'
        attempt = 0
        while True:
            attempt += 1
            response = requests.post(
                self.endpoint, headers=headers, json=payload,
                timeout=timeout, stream=True,
            )
            if response.status_code == 200:
                break
            err_text = response.text or ''
            if (
                response.status_code == 400
                and attempt == 1
                and payload.pop('stream_options', None) is not None
                and 'stream_options' in err_text
            ):
                continue
            self._raise_http(response)
        text = ''
        calls = {}
        usage = {}
        try:
            for raw in response.iter_lines():
                if not raw:
                    continue
                line = raw.decode('utf-8', errors='replace').strip()
                if line.startswith('data:'):
                    line = line[5:].strip()
                if not line or line == '[DONE]':
                    if line == '[DONE]':
                        break
                    continue
                try:
                    chunk = json.loads(line)
                except ValueError:
                    continue
                got = chunk.get('usage')
                if isinstance(got, dict) and got:
                    usage = got
                choices = chunk.get('choices') or []
                delta = (choices[0].get('delta') or {}) if choices else {}
                piece = delta.get('content') or ''
                if piece:
                    text += piece
                    yield {'text': piece}
                for tc in delta.get('tool_calls') or []:
                    idx = tc.get('index', 0)
                    row = calls.setdefault(idx, {
                        'id': '',
                        'type': 'function',
                        'function': {'name': '', 'arguments': ''},
                    })
                    if tc.get('id'):
                        row['id'] = tc['id']
                    fn = tc.get('function') or {}
                    if fn.get('name'):
                        row['function']['name'] += fn['name']
                    if fn.get('arguments'):
                        row['function']['arguments'] += fn['arguments']
        finally:
            response.close()
        message = {'role': 'assistant', 'content': text}
        if calls:
            message['tool_calls'] = [calls[i] for i in sorted(calls)]
        yield {'done': True, 'message': message, 'usage': usage}
