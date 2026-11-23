# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Generic skill runtime: bootstrap, fast-path, and presenters.

The engine is domain-agnostic. Domain logic lives in the skill's
``code_body`` (in its own module). This file only has generic mechanisms.

Contract (any skill)
--------------------
``code_body`` may return a ``result`` dict with:

- ``propose_steps``: Safe Plan list. If every step is auto-confirmable
  (``fetch_url`` on the whitelist **or** ``api_call`` to a ``trusted``
  server), the server runs them with no extra LLM round and no toast.
- ``continue``: if true and ``propose_steps`` ran, the engine calls
  ``code_body`` again with results in the ``previous_result`` global so
  a skill can chain dependent phases across rounds.
- ``presentation`` / ``__return_direct__`` plus ``data``|``groups``|
  ``sections``|``tables``|``formatted_text``: ready reply → HTML to chat
  without tools. The skill also composes its ``footer`` (the engine does
  not invent footers).
- Generic arg wait: help markdown card with no rows + invoke with no
  args → the next human message without a slash resumes the skill.
  Explicit ``__await_skill_args__`` True/False forces or skips the wait.
  Help (``?``) never waits.
- ``__skill_state__``: free dict the skill wants back next round. It
  returns as the sandbox global ``skill_state`` (``{}`` on a new invoke).
  The engine transports it without looking inside: slots and completeness
  are the skill's decision, not the engine's.
- Free metadata for the LLM when there is no fast-path.

Presenters (optional): generic ``register_presenter`` so a module can
add post-fetch formatters. The engine ships none.
"""

from __future__ import annotations
import json
import logging

from .skill_runtime_param_schema import (
    apply_code_keys_to_rows,
    assign_extracted_keys_to_rows,
    capture_help_text,
    drop_result_param_keys,
    fill_capture_params,
    help_without_turn_chips,
    infer_arg_hint_from_schema,
    infer_param_keys_from_code,
    infer_param_schema_from_code,
    infer_type_from_default,
    is_placeholder_skill_help,
    _is_slash_param_key,
    overlay_rows_on_schema,
    param_rows_fingerprint,
    param_rows_need_author,
    param_rows_to_prose,
    param_rows_to_schema,
    param_schema_to_json,
    _param_value_resolved,
    parse_param_schema_txt,
    schema_to_param_rows,
)

from .skill_runtime_help_prompts import (
    build_param_author_prompt,
    build_param_help_prompt,
    build_skill_help_user,
    ground_choices_on_spec,
    inject_unread_param_reads,
    merge_authored_param_schema,
    parse_param_author_help,
    parse_param_author_json,
    procedure_for_help,
    _PROCEDURE_TEMPLATE,
    schema_keys_that_need_place,
    schema_keys_unread_by_code,
    skill_help_fingerprint,
)

from .skill_runtime_code_rewrite import (
    accept_rewritten_code,
    bind_code_to_schema_params,
    build_code_param_rewrite_prompt,
    drop_schema_literal_assigns,
    parse_rewritten_skill_code,
    query_head_for_param_rewrite,
    schema_params_need_place,
    split_page_html_skill_code,
)

from .skill_runtime_read_values import (
    attach_schema_choices,
    build_param_extraction_prompt,
    deterministic_schema_hits,
    parse_and_validate_params,
)

from .skill_runtime_bind_args import (
    apply_schema_defaults,
    apply_schema_ordinals,
    empty_args_need_required_ask,
    enrich_params_with_dates,
    finalize_skill_params,
    leftover_free_text,
    merge_hybrid_params,
    missing_required_params,
    named_schema_params,
    normalize_unresolved_key,
    overlay_resolved_params,
    param_cache_payload,
    parse_param_cache_json,
    parse_skill_arguments,
    relative_param_keys,
    schema_needs_ai_resolution,
    schema_required_keys,
    skill_args_unmapped,
)

_logger = logging.getLogger(__name__)


# Callables: (exec_result, steps=None, meta=None) -> presentation dict | None
_PRESENTERS = []


def register_presenter(fn):
    """Decorator / registry of deterministic post-fetch formatters."""
    if fn not in _PRESENTERS:
        _PRESENTERS.append(fn)
    return fn


def skill_code_refusal(code, skill_code='skill'):
    """Why this code_body may not run, or empty.

    Checked on save and again on every run: a row saved before a rule was
    tightened still runs with the caller's rights.
    """
    from odoo import _
    from ..controllers.validators import validate_relaxaicode_source_ast

    ok, err, writes = validate_relaxaicode_source_ast(code)
    if not ok:
        return _(
            'The code of skill «%s» breaks the sandbox rules:\n\n%s'
        ) % (skill_code or '?', err)
    if writes:
        return _(
            'The code of skill «%s» writes to the database. A skill only '
            'reads; changes go in propose_steps and the user confirms them.'
        ) % (skill_code or '?')
    return ''


def _records_onto(value, env):
    """``value`` with every recordset moved onto ``env``.

    The body ran on box A's cursor, which closes before the result is shown.
    """
    from odoo.models import BaseModel
    if isinstance(value, BaseModel):
        return value.with_env(env)
    if isinstance(value, dict):
        return {k: _records_onto(v, env) for k, v in value.items()}
    if type(value) in (list, tuple, set):
        return type(value)(_records_onto(v, env) for v in value)
    return value


def bootstrap_skill_code_body(env, code, arguments='', skill_code='skill',
                              extra_params=None, previous_result=None,
                              diag=None, param_schema=None):
    """Run code_body in the safe sandbox. Returns the ``result`` dict or None.

    ``extra_params`` (optional): keys already resolved by the schema. They are merged
    over the parse. If there is any schema key, ``arguments`` and ``lugar``
    no longer carry the sentence: the skill does not read it again. A value
    of None only makes sure the key exists.

    ``previous_result`` (optional): results of the ``fetch_url`` steps run in
    the previous round (see ``try_skill_fast_path``). It is injected as the global
    ``previous_result`` (None on round 1) so a skill can orchestrate several
    dependent phases (e.g. geocode → forecast → present) WITHOUT the
    engine knowing anything about the domain.

    ``diag`` (optional dict): if ``code_body`` raises, the exception is stored
    in ``diag['bootstrap_error']`` so the error shown to the user is
    actionable (not a silent fallback).
    """
    code = (code or '').strip()
    if not code:
        return None
    refused = skill_code_refusal(code, skill_code)
    if refused:
        if isinstance(diag, dict):
            diag['bootstrap_error'] = refused
        _logger.warning('Skill bootstrap refused for %s: %s', skill_code, refused)
        return None
    from .skill_param_tokens import expand_skill_param_values
    params = parse_skill_arguments(arguments)
    enrich_params_with_dates(params)
    params = overlay_resolved_params(params, extra_params)
    params = expand_skill_param_values(params, env)
    live = [
        key for key, val in params.items()
        if _is_slash_param_key(key) and val not in (None, '', [])
    ]
    if param_schema:
        code = bind_code_to_schema_params(code, param_schema, env)
    elif live:
        code = drop_schema_literal_assigns(code, live)
    try:
        from ..controllers.context_builder import (
            build_safe_context,
            compile_sandbox,
        )
        from ..controllers.controller_helpers import open_readonly_env

        class _Ctrl(object):
            def __init__(self, _env):
                self.env = _env

            def _get_env_for_operation(self, _op):
                return self.env

            def _get_user_locale(self):
                # Same cascade as the rest of MCP: session → user → en_US
                try:
                    from odoo.http import request as http_request
                    ctx_lang = (
                        http_request.env.context.get('lang')
                        if http_request and getattr(http_request, 'env', None)
                        else None
                    )
                except Exception:
                    ctx_lang = None
                try:
                    return (
                        ctx_lang
                        or self.env.context.get('lang')
                        or self.env.user.lang
                        or 'en_US'
                    )
                except Exception:
                    return 'en_US'

        # Box A, like relaxaicode: a READ ONLY cursor of its own, rolled back
        # and closed here. The caller's cursor can write; the skill never holds it.
        ro_env, ro_cr = open_readonly_env(env)
        try:
            ctx = build_safe_context(
                _Ctrl(ro_env), 'read', previous_result=previous_result,
            )
            ctx.setdefault('previous_result', None)
            for key, val in params.items():
                ctx[key] = val
            exec(compile_sandbox(code, '<skill:%s>' % (skill_code or 'x')), ctx, ctx)
            result = _records_onto(ctx.get('result'), env)
        finally:
            try:
                ro_cr.rollback()
            finally:
                ro_cr.close()
        if isinstance(result, dict):
            # Skill-authored help/ask cards: stamp trust so report mode can
            # paint HTML without rejecting formatted_text as sandbox junk.
            if result.get('formatted_text') and (
                result.get('__return_direct__')
                or result.get('__stop_after_direct__')
            ):
                result.setdefault('__fmt_type__', 'author_html')
            return result
        # Single contract (see norm §4): code_body MUST assign a dict to
        # `result`. Any other shape is a skill error, not something the
        # engine should guess/wrap. It is reported with a clear reason.
        if isinstance(diag, dict):
            from odoo import _
            diag['result_not_dict'] = True
            diag['result_type'] = type(result).__name__
            diag['bootstrap_error'] = _(
                "code_body assigned `result` of type %s; the contract requires a dict "
                "(data / groups / formatted_text / propose_steps)."
            ) % type(result).__name__
        return None
    except Exception as exc:
        from .skill_errors import friendly_skill_error
        friendly = friendly_skill_error(exc, env)
        if isinstance(diag, dict):
            diag['bootstrap_error'] = friendly
        _logger.warning(
            'Skill bootstrap failed for %s: %s: %s',
            skill_code, type(exc).__name__, exc,
        )
        return None


def collect_external_sources(steps):
    """Hosts / API labels of Safe Plan steps or results.

    fetch_url → hostname; api_call / mcp_call → ``API: server/tool``.
    Skips steps with no data or with ``success=False``. Domain-agnostic.
    """
    from urllib.parse import urlparse
    out = set()
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        if step.get('success') is False:
            continue
        op = step.get('op')
        if op == 'fetch_url' and step.get('url'):
            try:
                host = urlparse(step['url']).hostname
                if host:
                    out.add(host)
            except Exception:
                pass
        elif op in ('api_call', 'mcp_call') and step.get('server'):
            srv = step.get('server')
            tool = step.get('tool')
            out.add('API: %s/%s' % (srv, tool) if tool else 'API: %s' % srv)
    return sorted(out)


def _has_presentable_payload(pres):
    """True if dict already carries a renderable envelope for direct return."""
    if not isinstance(pres, dict):
        return False
    return (
        pres.get('data') is not None
        or pres.get('groups') is not None
        or pres.get('sections') is not None
        or pres.get('tables') is not None
        or bool(pres.get('formatted_text'))
        or bool(pres.get('card'))
        or bool(pres.get('cards'))
    )


def _stamp_author_html(pres):
    """Platform trust mark for skill-authored HTML (not free LLM sandbox)."""
    if isinstance(pres, dict) and pres.get('formatted_text'):
        if not pres.get('__fmt_type__'):
            pres['__fmt_type__'] = 'author_html'
    return pres


def presentation_from_bootstrap(bootstrap):
    """If code_body already left a presentation, return it.

    A presentable envelope (``formatted_text`` / ``data`` / ``groups`` /
    ``sections`` / ``tables``) is enough. ``__return_direct__`` is optional
    (captured skills often omit it). ``propose_steps`` wins: do not paint
    a leftover card and skip the fetch round.
    """
    if not isinstance(bootstrap, dict):
        return None
    pres = bootstrap.get('presentation')
    if _has_presentable_payload(pres):
        return _stamp_author_html(dict(pres))
    steps = bootstrap.get('propose_steps')
    if isinstance(steps, list) and steps:
        return None
    if _has_presentable_payload(bootstrap):
        return _stamp_author_html(dict(bootstrap))
    return None


def _has_row_payload(presentation):
    """True when the envelope already carries row/group/table data."""
    if not isinstance(presentation, dict):
        return False
    for key in ('data', 'items', 'groups', 'sections', 'tables'):
        val = presentation.get(key)
        if isinstance(val, list) and val:
            return True
    return False


def skill_state_from_params(raw):
    """Decode the state a skill left behind (session JSON blob or dict).

    Never raises: a corrupt or foreign blob simply means "no state".
    """
    params = raw
    if isinstance(params, (bytes, bytearray)):
        params = params.decode('utf-8', 'ignore')
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except Exception:
            return {}
    if not isinstance(params, dict):
        return {}
    state = params.get('state')
    return dict(state) if isinstance(state, dict) else {}


def skill_state_for_await(*sources):
    """First non-empty ``__skill_state__`` among the given dicts."""
    for src in sources:
        if not isinstance(src, dict):
            continue
        state = src.get('__skill_state__')
        if isinstance(state, dict) and state:
            return dict(state)
    return {}


def should_await_skill_args(presentation, arguments='', is_help=False,
                            accepts_args=True, args_policy=None):
    """Whether the next non-slash human reply should resume this skill.

    Invariant (no domain): a direct HTML card with no tabular payload, after
    an invocation that did not already carry args, is asking for them.
    A skill that declares no parameters (``accepts_args`` False) cannot be
    waiting for any, so its empty states never turn sticky and never swallow
    the next free-chat message.

    Handing back ``__skill_state__`` also means "I expect a follow-up": that is
    how a multi-question skill stays in the conversation on rounds 2..N, where
    the args are no longer empty. Drop the state (or set the flag to False) on
    the round that finishes the job.

    Explicit ``__await_skill_args__`` True/False overrides. Help never awaits.
    """
    if is_help:
        return False
    if not isinstance(presentation, dict):
        return False
    flag = presentation.get('__await_skill_args__')
    if flag is False:
        return False
    if flag is True:
        return True
    if skill_state_for_await(presentation):
        return True
    policy = (args_policy or '').strip() or 'default'
    if policy in ('default', 'none'):
        return False
    if not accepts_args:
        return False
    if (arguments or '').strip():
        return False
    if not (presentation.get('formatted_text') or '').strip():
        return False
    return not _has_row_payload(presentation)


def try_present(exec_result, steps=None, meta=None):
    """Try registered presenters; the first that returns a dict wins.

    The engine ships none (domain-agnostic). A module
    may add its own with ``register_presenter``. With no presenters, it returns
    None and the result goes to the LLM to present it.
    """
    meta = meta or {}
    for fn in list(_PRESENTERS):
        try:
            out = fn(exec_result, steps=steps, meta=meta)
            if _has_presentable_payload(out):
                out = dict(out)
                out.setdefault('__return_direct__', True)
                out.setdefault('__stop_after_direct__', True)
                return _stamp_author_html(out)
        except Exception as exc:
            _logger.debug('skill presenter %s skipped: %s', fn, exc)
    return None


def render_presentation_html(presentation, env=None):
    """Dict presentation → chat HTML (or None). Avoids a circular import with agent_engine."""
    if not isinstance(presentation, dict):
        return None
    presentation = _stamp_author_html(dict(presentation))
    presentation.setdefault('__return_direct__', True)
    presentation.setdefault('__stop_after_direct__', True)
    try:
        from .relaxaicode_render import (
            render_context_from_env,
            render_for_direct_return,
            render_result_html,
            is_tabulable,
            _result_items,
            wrap_bare_images_clickable,
        )
        from .relaxaicode_render_cards import render_svg_cards_html
        render_ctx = render_context_from_env(env, result=presentation) if env is not None else None
        ft = presentation.get('formatted_text')
        cards = ''
        if not (ft and 'data-ai-card' in ft):
            cards = render_svg_cards_html(presentation, render_context=render_ctx) or ''
        if ft:
            return wrap_bare_images_clickable(ft, env=env) + cards
        rendered = render_for_direct_return(
            presentation,
            presentation.get('summary') or '',
            render_context=render_ctx,
        )
        if not rendered and _result_items(presentation) and is_tabulable(presentation):
            rendered = render_result_html(
                presentation,
                presentation.get('summary') or '',
                render_context=render_ctx,
            )
        if rendered or cards:
            return (rendered or '') + cards
    except Exception as exc:
        _logger.debug('render_presentation_html failed: %s', exc)
    return None


def try_skill_fast_path(env, bootstrap, title='Skill', *, code=None,
                        arguments='', skill_code='skill', extra_params=None,
                        max_rounds=5, diag=None, probe=False,
                        param_schema=None):
    """Run a skill's deterministic cycle without the LLM.

    Generic and domain-agnostic. On each round ``code_body`` (already
    run in ``bootstrap`` the first time) returns:

    - a **direct presentation** (``presentation`` / ``__return_direct__``
      with ``data``|``groups``|``sections``|``tables``|``formatted_text``)
      → rendered to HTML, done;
    - or ``propose_steps`` **CRUD / mixed** → creates a pending ``ai.safe.operation``
      and returns ``verification_id`` (+ short HTML) for the Confirm toast;
    - or ``propose_steps`` **only auto-confirmable steps** (``fetch_url`` on the
      whitelist or ``api_call`` to a ``trusted`` server); the engine runs them and,
      if the skill set ``continue`` true, calls the
      ``code_body`` again with the **accumulated** results in the global
      ``previous_result`` (next round). So the skill chains phases
      (geocode → fetch → present) without the engine knowing
      the domain.

    Returns ``{html, presentation, verification_id, plan, danger_level, title,
    exec_payload}`` or None if it does not apply. In skills with ``code_body``, a bail
    shows as a clear error (no fallback to ReAct).

    ``code`` is the skill's ``code_body``; if None, only the round already
    given in ``bootstrap`` is evaluated (compatibility: no re-run).

    ``diag`` (optional dict): filled with ``reason`` (why it fell back
    to the LLM) and ``round`` so the log can be diagnosed WITHOUT guessing.

    ``probe``: a plan that needs the toast returns ``needs_confirmation``
    instead of creating the pending operation, which is committed on a cursor
    of its own and would outlive the caller's rollback.
    """
    def _bail(reason):
        if isinstance(diag, dict):
            diag['reason'] = reason
            diag['round'] = round_i
        _logger.info('skill fast-path bail [%s]: %s', skill_code, reason)
        return None

    round_i = 0
    if not isinstance(bootstrap, dict):
        return _bail('bootstrap_not_dict')

    try:
        from ..controllers.safe_plan import (
            _all_steps_auto_confirmable,
            request_safe_plan,
            execute_safe_plan,
            validate_safe_plan,
        )
    except Exception as exc:
        return _bail('safe_plan_import_error: %s' % exc)

    prev = None
    for round_i in range(max_rounds):
        if round_i > 0:
            if not code:
                return _bail('no_code_body_for_next_round')
            _bd = {}
            bootstrap = bootstrap_skill_code_body(
                env, code, arguments=arguments, skill_code=skill_code,
                extra_params=extra_params, previous_result=prev, diag=_bd,
                param_schema=param_schema,
            )
            if not isinstance(bootstrap, dict):
                err = _bd.get('bootstrap_error')
                return _bail('reexec_not_dict'
                             + (': %s' % err if err else ''))

        # 1) Does the skill already bring a ready presentation?
        direct = presentation_from_bootstrap(bootstrap)
        if direct:
            html = render_presentation_html(direct, env=env)
            if html:
                return {
                    'html': html,
                    'presentation': direct,
                    'verification_id': None,
                    'exec_payload': prev,
                    'sources': collect_external_sources(prev),
                }
            return _bail('presentation_no_html')

        # 2) Does it propose steps?
        steps = bootstrap.get('propose_steps')
        if not isinstance(steps, list) or not steps:
            keys = sorted(bootstrap.keys())
            if not keys:
                return _bail('empty_result')
            return _bail('no_propose_steps(keys=%s)' % keys)

        ok, err = validate_safe_plan(steps, env)
        if not ok:
            return _bail('invalid_plan: %s' % err)

        # Plans that cannot auto-confirm (CRUD, non-trusted URL/API) → toast.
        # Trusted fetch_url + trusted api_call run here (multi-round).
        if not _all_steps_auto_confirmable(env, steps):
            if probe:
                return {'needs_confirmation': True, 'verification_id': None}
            pending = request_safe_plan(
                env, steps,
                title=bootstrap.get('title') or title,
                tool_name='skill:%s' % skill_code,
            )
            if not pending.get('success'):
                return _bail('pending_create_failed: %s'
                             % (pending.get('error') or 'unknown'))
            n_steps = len(steps)
            html = (
                'Prepared <b>%s</b> supervised step(s). '
                '<b>Confirm the toast in Odoo</b> to apply them.'
            ) % n_steps
            return {
                'html': html,
                'presentation': None,
                'verification_id': pending['verification_id'],
                'plan': pending.get('plan') or [],
                'danger_level': pending.get('danger_level') or 'medium',
                'title': pending.get('title') or title,
                'exec_payload': prev,
                'sources': collect_external_sources(prev or steps),
            }

        try:
            round_results = execute_safe_plan(env, steps)
        except Exception as exc:
            from .skill_errors import friendly_skill_error
            _logger.warning(
                'Skill fast-path exec failed for %s: %s: %s',
                skill_code, type(exc).__name__, exc,
            )
            return _bail(friendly_skill_error(exc, env))

        # Accumulate the results of every round so the skill can
        # paginate (e.g. several api_call) and present with the full history.
        if prev is None:
            prev = round_results
        elif isinstance(prev, list) and isinstance(round_results, list):
            prev = prev + round_results
        else:
            prev = round_results

        # Without ``continue`` the skill has no presentation phase of its own: the
        # engine has no domain presenter, so it falls back to the LLM.
        if not bootstrap.get('continue'):
            return _bail('no_continue_no_presentation')

    return _bail('max_rounds_exhausted')


_FAST_PATH_PUBLISH_BLOCKERS = frozenset((
    'presentation_no_html',
    'empty_result',
    'max_rounds_exhausted',
    'no_continue_no_presentation',
))


def check_skill_fast_path_publishable(
    env, code, arguments='', args_policy='default', param_schema='',
    skill_code='skill',
):
    """Return a user-facing error when ``/slash`` would fail with empty args.

    Returns ``None`` when publishable or when empty-args validation does not
    apply (required parameters, bootstrap exception, install-time registry).
    """
    body = (code or '').strip()
    if not body or env is None:
        return None
    if (getattr(env, 'context', None) or {}).get('skill_skip_body_check'):
        return None
    if not getattr(env.registry, 'ready', False):
        return None
    policy = (args_policy or 'default').strip() or 'default'
    if policy != 'none':
        schema = parse_param_schema_txt(param_schema or '')
        if schema_required_keys(schema):
            return None
    diag = {}
    try:
        # A publish check must not open a page or spend a design call.
        # Untrusted: a trusted server's write waits, so a writing skill is refused.
        check_env = env(context=dict(
            env.context, skill_publish_check=True, pns_ai_untrusted_turn=True,
        ))
        bootstrap = bootstrap_skill_code_body(
            check_env, body, arguments=arguments, skill_code=skill_code,
            diag=diag, param_schema=param_schema,
        )
    except Exception:
        return None
    if not isinstance(bootstrap, dict):
        return None
    fast = try_skill_fast_path(
        check_env, bootstrap, code=body, arguments=arguments,
        skill_code=skill_code, diag=diag, probe=True,
        param_schema=param_schema,
    )
    from odoo import _
    label = skill_code or 'skill'
    if isinstance(fast, dict) and fast.get('needs_confirmation'):
        return _(
            'Skill "%s" needs supervised safe-plan confirmation (toast). '
            'Capture only auto-confirmable fetch_url or trusted api_call '
            'steps, or edit the Code before publishing.'
        ) % label
    if fast is not None:
        return None
    reason = (diag or {}).get('reason') or ''
    if reason in _FAST_PATH_PUBLISH_BLOCKERS:
        return _(
            'Skill "%s" would fail on /slash with no arguments (%s). '
            'The Code must fetch live data on each run and include every '
            'phase from the source turn (fetch, transform, present).'
        ) % (label, reason)
    return None
