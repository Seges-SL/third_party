# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
from odoo import models, fields, api, _

from ..utils import context_roles
from ..utils.ai_agent_registry import MCP_BARE_AGENT_CODE

# Rule of thumb used by LLM tooling: ~4 UTF-8 bytes per token.
_BYTES_PER_TOKEN = 4


class AIContextStatsWizard(models.TransientModel):
    _name = 'pns_ai_mcp.context_stats_wizard'
    _description = 'MCP Context Statistics'

    agent_id = fields.Many2one(
        'ai.agent', string='Agent', readonly=True, ondelete='cascade',
    )
    inject_enabled = fields.Boolean(
        string='Turn-scoped domain packs',
        readonly=True,
        help='Mirrors Settings → AI Engine. Marks which bundle the live '
             'cache uses. Size columns always compare full linked vs '
             'discovery-optimized (same assembler), even when the flag is off.',
    )
    show_ktokens = fields.Boolean(
        string='Show kTok (≈4 B/token)',
        default=True,
        help='When checked, sizes use approximate kTok '
             '(bytes ÷ 4 ÷ 1000). Uncheck to show kilobytes.',
    )
    stats_html = fields.Html(string='', readonly=True, sanitize=False)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        Agent = self.env['ai.agent']
        agent = Agent.search(
            [('code', '=', MCP_BARE_AGENT_CODE)], limit=1,
        )
        as_ktokens = bool(res.get('show_ktokens'))
        if agent:
            res['agent_id'] = agent.id
            res['inject_enabled'] = agent._domain_index_inject_enabled()
            res['stats_html'] = self._html_for_agent(
                agent, as_ktokens=as_ktokens,
            )
        else:
            Context = self.env['ai.context']
            res['inject_enabled'] = Context._domain_index_inject_enabled()
            res['stats_html'] = self._html_catalog_fallback(
                as_ktokens=as_ktokens,
            )
        return res

    @api.onchange('show_ktokens')
    def _onchange_show_ktokens(self):
        if self.agent_id:
            self.inject_enabled = self.agent_id._domain_index_inject_enabled()
            self.stats_html = self._html_for_agent(
                self.agent_id, as_ktokens=bool(self.show_ktokens),
            )
        else:
            self.inject_enabled = (
                self.env['ai.context']._domain_index_inject_enabled()
            )
            self.stats_html = self._html_catalog_fallback(
                as_ktokens=bool(self.show_ktokens),
            )

    @api.model
    def _stats_split_linked(self, linked, user_locale=None):
        """Split by discovery index always (flag does not collapse columns).

        Monolithic = all linked shared contexts.
        Optimized = linked minus discovery-indexed codes.
        """
        Context = self.env['ai.context']
        indexed = Context.sudo().get_discovery_indexed_codes(user_locale)
        if not indexed:
            return linked, linked, set()

        def _is_indexed(ctx):
            return (ctx.base_code or ctx.code) in indexed or ctx.code in indexed

        opt = linked.filtered(lambda c: not _is_indexed(c))
        return linked, opt, indexed

    @api.model
    def _html_for_agent(self, agent, as_ktokens=False):
        agent.ensure_one()
        Context = self.env['ai.context']
        user_locale = self.env.context.get('lang', 'en_US')
        inject = agent._domain_index_inject_enabled()
        linked = (
            agent.context_ids.filtered('active') | agent._system_contexts()
        ).filtered(lambda c: not c.owner_id)
        mono_contexts, opt_contexts, indexed = self._stats_split_linked(
            linked, user_locale=user_locale,
        )
        mono_comp = Context.get_composition_stats(
            mono_contexts, user_locale=user_locale,
        )
        opt_comp = Context.get_composition_stats(
            opt_contexts, user_locale=user_locale,
        )
        cache_error = None
        mono_size = opt_size = 0
        try:
            # Same assembler for both columns (never mix get_content here).
            mono_size = Context.get_bundle_payload_size(
                mono_contexts, user_locale,
            )
            opt_size = Context.get_bundle_payload_size(
                opt_contexts, user_locale,
            )
        except Exception as e:
            cache_error = str(e)
        title = '%s (%s)' % (
            agent.display_name or agent.code,
            agent.code or '',
        )
        return self._build_stats_html(
            user_locale=user_locale,
            title=title,
            inject_enabled=inject,
            mono_comp=mono_comp,
            mono_size=mono_size,
            opt_comp=opt_comp,
            opt_size=opt_size,
            turn_scoped_codes=sorted(indexed) if indexed else [],
            cache_error=cache_error,
            as_ktokens=as_ktokens,
        )

    @api.model
    def _html_catalog_fallback(self, as_ktokens=False):
        Context = self.env['ai.context']
        user_locale = self.env.context.get('lang', 'en_US')
        inject = Context._domain_index_inject_enabled()
        all_inj = Context._injectable_active_contexts()
        mono, opt, indexed = self._stats_split_linked(
            all_inj, user_locale=user_locale,
        )
        cache_error = None
        mono_size = opt_size = 0
        try:
            mono_size = Context.get_bundle_payload_size(mono, user_locale)
            opt_size = Context.get_bundle_payload_size(opt, user_locale)
        except Exception as e:
            cache_error = str(e)
        return self._build_stats_html(
            user_locale=user_locale,
            title=_('Catalog (no MCP agent)'),
            inject_enabled=inject,
            mono_comp=Context.get_composition_stats(mono, user_locale=user_locale),
            mono_size=mono_size,
            opt_comp=Context.get_composition_stats(opt, user_locale=user_locale),
            opt_size=opt_size,
            turn_scoped_codes=sorted(indexed) if indexed else [],
            cache_error=cache_error,
            as_ktokens=as_ktokens,
        )

    @api.model
    def _fmt_size(self, size_bytes, as_ktokens=False, decimals=2):
        size_bytes = size_bytes or 0
        if as_ktokens:
            ktok = size_bytes / float(_BYTES_PER_TOKEN) / 1000.0
            if ktok >= 1000:
                num = f'{ktok / 1000.0:,.{decimals}f}'.replace(',', '.')
                return '%s MTok' % num
            num = f'{ktok:,.{decimals}f}'.replace(',', '.')
            return '%s kTok' % num
        if size_bytes == 0:
            return '0 B'
        kb = size_bytes / 1024.0
        if kb < 1024:
            return f'{kb:,.{decimals}f} KB'.replace(',', '.')
        return f'{kb / 1024:,.{decimals}f} MB'.replace(',', '.')

    @api.model
    def _composition_table(self, comp, total_label, as_ktokens=False):
        categories = list(context_roles.INJECTABLE_TYPES)
        labels = {
            'core': 'core',
            'domain': 'domain',
            'locale': 'locale',
        }
        fmt = lambda n: self._fmt_size(n, as_ktokens=as_ktokens)
        rows = []
        for cat in categories:
            row = comp['categories'][cat]
            if not row['count']:
                continue
            rows.append(
                '<tr>'
                f'<td>{labels.get(cat, cat)}</td>'
                f'<td class="text-center">{row["count"]}</td>'
                f'<td class="text-end text-right">{fmt(row["size_raw"])}</td>'
                f'<td class="text-end text-right"><b>{fmt(row["size_optimized"])}</b></td>'
                '</tr>'
            )
        rows.append(
            '<tr class="fw-bold font-weight-bold table-active">'
            f'<td>{total_label}</td>'
            f'<td class="text-center">{comp["total_count"]}</td>'
            f'<td class="text-end text-right">{fmt(comp["total_size_raw"])}</td>'
            f'<td class="text-end text-right">{fmt(comp["total_size_optimized"])}</td>'
            '</tr>'
        )
        return (
            '<table class="table table-sm table-striped mb-0" '
            'style="table-layout:fixed;width:100%;margin:0;">'
            '<colgroup>'
            '<col style="width:40%"/><col style="width:12%"/>'
            '<col style="width:24%"/><col style="width:24%"/>'
            '</colgroup>'
            '<thead><tr>'
            f'<th>{_("Type")}</th>'
            f'<th class="text-center">{_("Qty")}</th>'
            f'<th class="text-end text-right">{_("Raw")}</th>'
            f'<th class="text-end text-right">{_("LLM")}</th>'
            '</tr></thead><tbody>'
            + ''.join(rows)
            + '</tbody></table>'
        )

    @api.model
    def _bundle_card(self, number, title, size_txt, body_html, active=False):
        if active:
            border, head_bg, head_bd = '#0d6efd', '#e7f1ff', '#b6d4fe'
            badge = (
                f' <span class="badge bg-primary text-white" '
                f'style="font-size:11px;">{_("ACTIVE CACHE")}</span>'
            )
        else:
            border, head_bg, head_bd = '#dee2e6', '#e9ecef', '#dee2e6'
            badge = ''
        return (
            f'<div style="border:2px solid {border};border-radius:4px;'
            f'margin-bottom:8px;overflow:hidden;">'
            f'<div style="padding:6px 10px;background:{head_bg};'
            f'border-bottom:1px solid {head_bd};">'
            f'<strong>{number}. {title}</strong>{badge}'
            f'<span class="text-muted"> — {size_txt}</span>'
            f'</div>'
            f'<div style="padding:6px 10px;">{body_html}</div></div>'
        )

    @api.model
    def _build_stats_html(
        self,
        user_locale,
        title=None,
        inject_enabled=None,
        mono_comp=None,
        mono_size=0,
        opt_comp=None,
        opt_size=0,
        turn_scoped_codes=None,
        cache_error=None,
        as_ktokens=False,
        **_legacy,
    ):
        fmt = lambda n: self._fmt_size(n, as_ktokens=as_ktokens)
        turn_scoped_codes = turn_scoped_codes or []
        saved = max(0, (mono_size or 0) - (opt_size or 0))
        unit_hint = (
            _('Sizes in approximate kTok (1 token ≈ 4 bytes).')
            if as_ktokens
            else _('Sizes in kilobytes.')
        )
        inject_on = bool(inject_enabled)

        html = [
            '<div class="mcp-context-stats" '
            'style="font-size:12px;line-height:1.35;">',
        ]
        meta = []
        if title:
            meta.append(title)
        meta.append(_('Locale: %s') % user_locale)
        meta.append(unit_hint)
        html.append(
            '<p class="text-muted" style="margin:0 0 6px 0;">'
            + ' · '.join(meta) + '</p>'
        )

        if inject_enabled is not None:
            if inject_on:
                bg, bd, fg = '#e8f5e9', '#198754', '#0f5132'
                head = _('Turn-scoped domain packs: ON')
                body = _('ACTIVE CACHE = Optimized (indexed packs on match).')
            else:
                bg, bd, fg = '#fff3cd', '#ffc107', '#664d03'
                head = _('Turn-scoped domain packs: OFF')
                body = _(
                    'ACTIVE CACHE = Monolithic. Columns still compare both sizes.'
                )
            html.append(
                f'<div style="padding:6px 10px;margin-bottom:8px;border-radius:4px;'
                f'border:2px solid {bd};background:{bg};color:{fg};">'
                f'<strong>{head}</strong>'
                f'<span style="margin-left:8px;font-size:12px;">{body}</span></div>'
            )

        if cache_error:
            html.append(
                f'<div class="alert alert-danger py-2">'
                f'<strong>{_("Error:")}</strong> {cache_error}</div></div>'
            )
            return ''.join(html)

        html.append(
            '<div style="display:flex;flex-wrap:wrap;gap:14px;margin-bottom:8px;'
            'padding:8px 10px;background:#f8f9fa;border-radius:4px;">'
            f'<div><div class="text-muted" style="font-size:11px;">'
            f'{_("Monolithic")}</div>'
            f'<div style="font-size:1.2em;font-weight:600;">{fmt(mono_size)}</div></div>'
            f'<div><div class="text-muted" style="font-size:11px;">'
            f'{_("Optimized (discovery)")}</div>'
            f'<div style="font-size:1.2em;font-weight:600;'
            f'color:{"#198754" if inject_on else "#212529"};">'
            f'{fmt(opt_size)}</div></div>'
            f'<div><div class="text-muted" style="font-size:11px;">'
            f'{_("Potential save")}</div>'
            f'<div style="font-size:1.2em;font-weight:600;">{fmt(saved)}</div></div>'
            '</div>'
        )

        mono_body = ''
        if mono_comp:
            mono_body = self._composition_table(
                mono_comp, _('TOTAL (monolithic)'), as_ktokens=as_ktokens,
            )
        html.append(self._bundle_card(
            '1', _('Monolithic bundle'), fmt(mono_size), mono_body,
            active=not inject_on,
        ))

        opt_body = ''
        if opt_comp:
            opt_body = self._composition_table(
                opt_comp, _('TOTAL (optimized)'), as_ktokens=as_ktokens,
            )
        if turn_scoped_codes:
            codes = ', '.join(turn_scoped_codes)
            opt_body += (
                '<details style="margin-top:6px;font-size:11px;">'
                f'<summary class="text-muted" style="cursor:pointer;">'
                f'{_("Indexed packs excluded (%s) — expand") % len(turn_scoped_codes)}'
                f'</summary>'
                f'<code style="font-size:11px;word-break:break-all;">{codes}</code>'
                f'</details>'
            )
        elif not turn_scoped_codes:
            opt_body += (
                '<div class="text-muted" style="font-size:11px;margin-top:4px;">'
                f'{_("No discovery-indexed packs on this agent composition.")}'
                '</div>'
            )

        html.append(self._bundle_card(
            '2', _('Optimized bundle (discovery)'), fmt(opt_size), opt_body,
            active=inject_on,
        ))

        footnote = _(
            'Raw = XML metadata included. LLM = stripped. '
            'Headline = assembled payload (same method both sides).'
        )
        html.append(
            '<p class="text-muted mb-0" style="font-size:10px;margin:0;">'
            f'{footnote}</p></div>'
        )
        return ''.join(html)
