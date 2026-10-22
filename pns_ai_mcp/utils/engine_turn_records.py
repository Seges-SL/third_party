# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""What one turn learned from its tools: records, sources, basket, downloads."""

import logging

from odoo import _

_logger = logging.getLogger(__name__)

_RECORDS_MAX = 50


class TurnRecordsMixin:
    """Part of ``AgentEngine``; only used through it."""

    def _absorb_export_result(self, turn, _ex):
        if not isinstance(_ex, dict):
            return []
        chips = []
        try:
            from .artifact_export import export_result_chips
            chips = export_result_chips(_ex)
        except Exception:
            chips = []
        if not chips:
            raw_chips = _ex.get('chips')
            if isinstance(raw_chips, list):
                chips = [
                    c for c in raw_chips
                    if isinstance(c, dict) and (c.get('url') or c.get('name'))
                ]
            else:
                chip = _ex.get('chip')
                if isinstance(chip, dict) and (
                    chip.get('url') or chip.get('name')
                ):
                    chips = [chip]
        for chip in chips:
            turn.export_chips.append(chip)
        tokens = _ex.get('refused_tokens')
        if isinstance(tokens, (list, tuple)) and tokens:
            turn.export_refused_tokens = list(tokens)
        return chips

    def _harvest_file_labels(self, *objs):
        labels = (self.env.context or {}).get('file_label_by_id')
        if not isinstance(labels, dict):
            return
        try:
            from .session_download import file_labels_from_mapping
            for obj in objs:
                if obj is not None:
                    file_labels_from_mapping(obj, labels)
        except Exception:
            pass

    def _absorb_plan_downloads(self, turn, steps):
        """Session chips from fetch_url/api_call; hide listing tables."""
        try:
            from .session_download import (
                collect_download_chips,
                file_labels_from_steps,
            )
            labels = (self.env.context or {}).get('file_label_by_id')
            if isinstance(labels, dict):
                file_labels_from_steps(steps, labels)
            chips = collect_download_chips(steps)
        except Exception:
            chips = []
        added = []
        for chip in chips:
            if isinstance(chip, dict) and (chip.get('url') or chip.get('name')):
                turn.export_chips.append(chip)
                added.append(chip)
        if not added:
            return False
        turn.export_attached = True
        try:
            from .artifact_export import wants_on_screen_blocks
            _show = wants_on_screen_blocks(
                turn.primary_artifact or turn.last_tabulable_payload,
            )
        except Exception:
            _show = False
        if _show:
            return False
        turn.direct_formatted = ''
        turn.stop_after_direct = True
        return True

    def _stamp_refused_note(self, turn):
        if not turn.export_chips or not turn.export_refused_tokens:
            return
        try:
            from .artifact_export import merge_refused_note
            turn.direct_formatted = merge_refused_note(
                turn.direct_formatted,
                turn.export_refused_tokens,
                note=_(
                    'These file types are not available as a session download: %s. I can send PDF, Excel, Word, text, Markdown, or HTML.'
                ),
            )
        except Exception:
            pass

    def _payload_for_screen(self, payload=None):
        """Stamp report_outline onto the payload used for hide/export.

        Lives outside the ReAct loop: a no-tool final answer (skill
        report) still calls this after ``while``, and a loop-local
        ``def`` is an UnboundLocalError.
        """
        try:
            from .artifact_export import payload_has_report_outline
        except Exception:
            payload_has_report_outline = lambda *_a, **_k: False
        outline = None
        rtp = getattr(self, '_report_tables_payload', None)
        if payload_has_report_outline(rtp):
            outline = rtp.get('report_outline')
        else:
            rc = getattr(self, '_report_contract', None) or {}
            if isinstance(rc, dict) and rc.get('report_outline'):
                outline = rc.get('report_outline')
        if payload_has_report_outline(payload) or not outline:
            return payload
        if isinstance(payload, dict):
            out = dict(payload)
            out['report_outline'] = outline
            return out
        return {'report_outline': outline}

    def _remember_clip_data(self, turn, payload=None, rows=None):
        if turn.export_clip_data:
            return
        try:
            from .artifact_export import clip_data_from_payload
            data = clip_data_from_payload(payload, rows)
        except Exception:
            data = None
        if data:
            turn.export_clip_data = data

    def _collect_sources(self, turn, steps):
        """Añade a external_sources las fuentes de una lista de pasos/resultados."""
        from .skill_runtime import collect_external_sources
        for _src in collect_external_sources(steps):
            turn.external_sources.add(_src)

    def _add_record(self, turn, model, rec_id, name=None, role=None):
        try:
            rec_id = int(rec_id)
        except (TypeError, ValueError):
            return
        # Validar contra el registro: descarta columnas espurias llamadas
        # 'model' que no son un modelo técnico real (p.ej. modelo de vehículo).
        if not model or not isinstance(model, str) or model not in self.env:
            return
        from .turn_record_models import remember_record
        remember_record(turn.turn_record_models, model, rec_id)
        key = (model, rec_id)
        if key in turn._records_seen or len(turn.collected_records) >= _RECORDS_MAX:
            return
        turn._records_seen.add(key)
        _nm = name if (name and isinstance(name, str)) else ('%s #%s' % (model, rec_id))
        rec = {'model': model, 'id': rec_id, 'name': _nm[:120]}
        if role:
            rec['role'] = role
        turn.collected_records.append(rec)

    def _learn_row_models(self, turn, rows):
        """Rows this turn already read say which model they belong to.

        The step that rebuilds them from a literal has no recordset left
        to ask, so without this the ids reach the screen as dead text.
        """
        try:
            from .turn_record_models import remember_rows
            remember_rows(turn.turn_record_models, rows)
        except Exception:
            _logger.debug('turn record models skipped', exc_info=True)

    def _collect_records_steps(self, turn, steps):
        """CRUD results: cite the document header, not a line or catalog row."""
        try:
            from .record_cite import resolve_document_target
        except Exception:
            resolve_document_target = None
        for _s in (steps or []):
            if not isinstance(_s, dict) or _s.get('success') is False:
                continue
            _model = _s.get('model')
            _name = _s.get('name')
            _rids = []
            if isinstance(_s.get('id'), int):
                _rids.append(_s.get('id'))
            if isinstance(_s.get('new_id'), int):
                _rids.append(_s.get('new_id'))
            if isinstance(_s.get('ids'), list):
                _rids.extend(_s.get('ids'))
            if resolve_document_target is None:
                continue
            for _i in _rids:
                tgt = resolve_document_target(_model, _i, env=self.env)
                if not tgt:
                    continue
                _lbl = _name if _model == tgt[0] else None
                self._add_record(turn, tgt[0], tgt[1], _lbl, role='document')

    def _basket_push(self, turn, payload, code=''):
        try:
            from .primary_artifact import apply as apply_primary
            turn.primary_artifact, _action = apply_primary(
                turn.primary_artifact,
                turn.turn_presentation_basket,
                payload,
                code,
            )
        except Exception:
            try:
                from .turn_presentation_basket import append_presentable
                append_presentable(turn.turn_presentation_basket, payload)
            except Exception:
                pass

    def _basket_html_for_replace(self, turn, html):
        """Merge presentable results; keep basket so the primary stays."""
        try:
            from .turn_presentation_basket import render_basket_html
            merged = render_basket_html(
                turn.turn_presentation_basket,
                fallback_html=html,
                env=self.env,
            )
        except Exception as _basket_exc:
            _logger.debug(
                'turn presentation basket skipped: %s', _basket_exc,
            )
            merged = html
        return merged if merged is not None else html
