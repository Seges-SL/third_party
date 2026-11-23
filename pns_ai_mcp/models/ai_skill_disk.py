# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""ai.skill: import factory skills from a module's disk, retire the gone ones, agent defaults."""

import logging
import os

from odoo import api, models, _
from odoo.exceptions import AccessError, UserError
from ..utils import mcp_ui as pns_ui
from ..utils.import_export_guard import ensure_ai_admin
from ..utils.skill_files import skill_code_body_path, split_skill_identity

_logger = logging.getLogger(__name__)


class AISkillDisk(models.Model):
    _inherit = 'ai.skill'

    @api.model
    def _factory_skill_rel_paths_on_disk(self):
        """``skills/<scope>/<file>.md`` paths that still exist in addons."""
        found = set()
        for _mod, base in self._get_skill_source_paths():
            for scope in ('system', 'custom'):
                scope_dir = os.path.join(base, scope)
                if not os.path.isdir(scope_dir):
                    continue
                for filename in os.listdir(scope_dir):
                    if filename.endswith('.md'):
                        found.add('skills/%s/%s' % (scope, filename))
        return found

    def _require_bootstrap(self):
        """Module seed and ``-u`` only.

        ``call_kw`` cannot set ``env.su`` or become the superuser. A context
        flag is not checked here.
        """
        if self.env.su or self.env.user._is_superuser():
            return
        raise AccessError(_(
            'Only the system can run this maintenance action.'
        ))

    # ------------------------------------------------------------------
    # File sync (parallel to mcp_context): ai/skills/system & ai/skills/custom
    # ------------------------------------------------------------------
    @api.model
    def _get_module_path(self):
        """Absolute path of the pns_ai_mcp module (dev or installed)."""
        try:
            from odoo.modules.module import get_module_path
            path = get_module_path('pns_ai_mcp')
            if path and os.path.exists(path):
                return path
        except Exception:
            pass
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    @api.model
    def _skill_parse_md(self, text):
        """Parse skills/<scope>/<code>.md front-matter: returns (meta_dict, body)."""
        meta = {}
        lines = (text or '').split('\n')
        if lines and lines[0].strip() == '---':
            i = 1
            while i < len(lines) and lines[i].strip() != '---':
                if ':' in lines[i]:
                    key, _, val = lines[i].partition(':')
                    meta[key.strip()] = val.strip()
                i += 1
            body = '\n'.join(lines[i + 1:])
            if body.startswith('\n'):
                body = body[1:]
            return meta, body
        return meta, text or ''

    @api.model
    def _get_skill_source_paths(self, module_name=None):
        """Return [(module_name, skills_dir)] for addons that ship ``ai/skills/``.

        Includes ``to upgrade`` / ``to install``: during a module's own ``-u``
        Odoo has already left ``installed``, so a seed that only scanned that
        state saw zero files and neither upserted nor pruned.

        Pass ``module_name`` to resolve that addon from disk even if its
        ``ir.module.module`` row is missing or in another state.
        """
        from odoo.modules.module import get_module_path
        from ..utils.ai_paths import module_kind_dir
        result = []
        want = (module_name or '').strip()
        Module = self.env['ir.module.module'].sudo()
        if want:
            mods = Module.search([('name', '=', want)])
        else:
            mods = Module.search([
                ('state', 'in', ('installed', 'to upgrade', 'to install')),
            ])
        seen = set()
        for mod in mods:
            mod_path = get_module_path(mod.name)
            if not mod_path:
                continue
            skills_dir = module_kind_dir(mod_path, 'skills')
            if skills_dir:
                result.append((mod.name, skills_dir))
                seen.add(mod.name)
        if want and want not in seen:
            mod_path = get_module_path(want)
            skills_dir = module_kind_dir(mod_path, 'skills') if mod_path else None
            if skills_dir:
                result.append((want, skills_dir))
        return result

    @api.model
    def import_from_files(
        self, replace_existing=True, only_codes=None, module_name=None,
        scopes=None,
    ):
        """Sync skills from module files (ai/skills/system & ai/skills/custom)
        into DB.

        Scans installed modules that ship an ``ai/skills/`` dir. Pass
        ``module_name`` to seed one addon (install/-u of that module).
        ``scopes`` defaults to both drawers; the engine factory seed
        passes ``('system',)`` so ``custom/`` is never planted here.

        replace_existing=True (default): overwrite skills whose code already
        exists (upsert), leaving the instance ``active`` flag. User-owned
        rows are skipped. ``import_from_module`` then drops factory leftovers
        whose ``.md`` is gone (not when the folder yielded no files).

        only_codes: optional iterable of skill codes to restrict the import to
        (used for the per-agent "restore from module" scope). Other files are
        skipped.
        """
        ensure_ai_admin(self.env)
        # Module→DB seed: authorised path (ensure_ai_admin already checked
        # the real user). sudo() opens the factory lock; the context flag
        # alone is not enough, because RPC can send it.
        self = self.sudo().with_context(
            skip_hardcoded_restrictions=True,
            skip_param_line_schema=True,
            skip_skill_form_author=True,
        )
        Agent = self.env['ai.agent']
        Context = self.env['ai.context']
        only_codes_set = set(only_codes) if only_codes else None
        stats = {
            'created': 0, 'updated': 0, 'skipped': 0, 'errors': [], 'pruned': 0,
            'missing_contexts': [], 'missing_agents': [],
        }
        want_mod = (module_name or '').strip()
        allowed = {
            str(s).strip() for s in (scopes or ('system', 'custom')) if s
        }
        walk = tuple(s for s in ('system', 'custom') if s in allowed)
        for source_mod, base in self._get_skill_source_paths(
            module_name=want_mod or None,
        ):
            for scope in walk:
                scope_dir = os.path.join(base, scope)
                if not os.path.isdir(scope_dir):
                    continue
                is_system = scope == 'system'
                for filename in sorted(os.listdir(scope_dir)):
                    if not filename.endswith('.md'):
                        continue
                    try:
                        with open(os.path.join(scope_dir, filename), 'r',
                                  encoding='utf-8') as fobj:
                            meta, body = self._skill_parse_md(fobj.read())
                        code, command = split_skill_identity(filename, meta)
                        invoke = command or code
                        if not code:
                            continue
                        if only_codes_set is not None and code not in only_codes_set:
                            if invoke not in only_codes_set:
                                continue
                        command_val = command or False
                        code_body = ''
                        py_path = skill_code_body_path(
                            scope_dir, filename, code, command or None,
                        )
                        if py_path and os.path.isfile(py_path):
                            with open(py_path, 'r', encoding='utf-8') as fobj:
                                code_body = fobj.read()
                        from ..utils.skill_engine_contract import (
                            skill_contract_violations,
                        )
                        unknown = skill_contract_violations(
                            meta=meta, code_body=code_body,
                        )
                        if unknown:
                            self._raise_unpublished_capability(code, unknown)
                        exclusive = self.env[
                            'ai.context'
                        ]._explicit_agent_codes_from_metadata(meta)
                        agent_codes = list(exclusive) if exclusive else []
                        agents = Agent.browse()
                        for ac in agent_codes:
                            found_agent = Agent.search([('code', '=', ac)], limit=1)
                            if found_agent:
                                agents |= found_agent
                            elif ac not in stats['missing_agents']:
                                stats['missing_agents'].append(ac)
                        # Pull: same as contexts — explicit codes, or @module
                        # for the whole drawer unless the skill is exclusive.
                        for agent in Agent.search([]):
                            if agent.wants_skill_code(
                                code,
                                source_module=source_mod,
                                pack_exclusive=exclusive is not None,
                            ):
                                agents |= agent
                        ctx_codes = [
                            c.strip() for c in (meta.get('context_codes') or '').split(',')
                            if c.strip()
                        ]
                        contexts = (
                            Context.search([('code', 'in', ctx_codes)])
                            if ctx_codes else Context.browse()
                        )
                        found = set(contexts.mapped('code'))
                        for missing in ctx_codes:
                            if missing not in found and missing not in stats['missing_contexts']:
                                stats['missing_contexts'].append(missing)
                        try:
                            sequence = int(meta.get('sequence') or 10)
                        except (TypeError, ValueError):
                            sequence = 10
                        active = str(meta.get('active', 'true')).strip().lower() != 'false'
                        body = (body or '').rstrip('\n')
                        vals = {
                            'name': meta.get('name') or code,
                            'description': meta.get('description') or code,
                            'content': body or (meta.get('description') or code),
                            'code_body': code_body or False,
                            'agent_ids': [(6, 0, agents.ids)],
                            'version': meta.get('version') or False,
                            'param_schema': (meta.get('param_schema') or '').strip() or False,
                            'arg_hint': (meta.get('arg_hint') or '').strip() or False,
                            'args_policy': self._args_policy_from_meta(meta),
                            'compose': self._compose_from_meta(meta),
                            'triggers': (meta.get('triggers') or '').strip() or False,
                            'sequence': sequence,
                            'active': active,
                            'is_system': is_system,
                            'source_module': source_mod,
                            'rel_path': 'skills/%s/%s' % (scope, filename),
                            'context_ids': [(6, 0, contexts.ids)],
                            'command': command_val,
                            'code': code,
                        }
                        if 'required_groups' in meta:
                            vals['required_group_ids'] = [
                                (6, 0, self._required_groups_from_meta(meta).ids),
                            ]
                        rel_path = vals['rel_path']
                        existing = self.search([
                            ('source_module', '=', source_mod),
                            ('rel_path', '=', rel_path),
                        ], limit=1)
                        if not existing:
                            existing = self.search([
                                '|', '|',
                                ('code', '=', code),
                                ('code', '=', invoke),
                                ('command', '=', invoke),
                            ], limit=1)
                        if existing:
                            if not replace_existing:
                                stats['skipped'] += 1
                                continue
                            # User-owned skills are never overwritten by module files.
                            if existing.owner_id:
                                stats['skipped'] += 1
                                _logger.info(
                                    'MCP: skip factory overwrite of user-owned '
                                    'skill %s (owner=%s)',
                                    existing.code, existing.owner_id.login,
                                )
                                continue
                            if (
                                existing.source_module
                                and existing.source_module != source_mod
                            ):
                                stats['skipped'] += 1
                                _logger.warning(
                                    'MCP: skip skill %s (owner=%s, attempted=%s)',
                                    code, existing.source_module, source_mod,
                                )
                                continue
                            # Keep operator slash visibility and the instance
                            # active flag across factory re-seed.
                            write_vals = {
                                k: v for k, v in vals.items()
                                if k not in ('show_in_slash', 'active')
                            }
                            existing.write(write_vals)
                            existing._apply_slash_hidden_from_icp()
                            stats['updated'] += 1
                        else:
                            vals['code'] = code
                            self.create(vals)
                            stats['created'] += 1
                    except Exception as exc:
                        stats['errors'].append('%s: %s' % (filename, exc))
        # Re-apply ICP hides in case create defaulted True after a full re-seed.
        try:
            hidden = self._slash_hidden_codes()
            if hidden:
                self.search([
                    '|',
                    ('code', 'in', list(hidden)),
                    ('command', 'in', list(hidden)),
                ])._apply_slash_hidden_from_icp()
        except Exception:
            _logger.debug(
                'MCP: could not re-apply slash-hidden ICP after skill import',
                exc_info=True,
            )
        # No pruning: import = upsert + recover only. System skills whose .md
        # was removed/renamed are kept (never deleted); remove leftovers by
        # hand if ever needed.
        _logger.info('MCP: skills import_from_files: %s', stats)
        try:
            self._fill_missing_param_lines()
        except Exception:
            _logger.debug(
                'MCP: could not fill skill param lines after import',
                exc_info=True,
            )
        self._after_factory_skill_import(stats)
        return stats

    @api.model
    def _skill_disk_index_for_module(self, module_name):
        """rel_path / code / command shipped by one addon's ``ai/skills/``."""
        from ..utils.skill_files import split_skill_identity
        rels, codes, commands = set(), set(), set()
        want = (module_name or '').strip()
        if not want:
            return rels, codes, commands
        for source_mod, base in self._get_skill_source_paths(module_name=want):
            if source_mod != want:
                continue
            for scope in ('system', 'custom'):
                scope_dir = os.path.join(base, scope)
                if not os.path.isdir(scope_dir):
                    continue
                for filename in os.listdir(scope_dir):
                    if not filename.endswith('.md'):
                        continue
                    rels.add('skills/%s/%s' % (scope, filename))
                    try:
                        with open(
                            os.path.join(scope_dir, filename),
                            encoding='utf-8',
                        ) as handle:
                            meta, _body = self._skill_parse_md(handle.read())
                    except OSError:
                        continue
                    code, command = split_skill_identity(filename, meta)
                    if code:
                        codes.add(code)
                    if command:
                        commands.add(command)
                    elif code:
                        commands.add(code)
        return rels, codes, commands

    @api.model
    def _unlink_retired_from_module(self, module_name):
        """Unlink factory rows of this addon whose ``.md`` is gone from disk.

        User-owned rows stay. Does nothing if the addon has no skill files
        (avoids wiping the catalog when the overlay is missing). A claimed
        leftover with a stale ``rel_path`` is kept if its code or slash
        still names a file on disk (import failed this pass ≠ retired).
        """
        self._require_bootstrap()
        from ..utils.skill_files import factory_row_on_disk
        name = (module_name or '').strip()
        if not name:
            return 0
        on_disk, disk_codes, disk_commands = self._skill_disk_index_for_module(
            name,
        )
        if not on_disk:
            _logger.warning(
                'MCP: skip retired unlink for %s (no skill files on disk)',
                name,
            )
            return 0
        Skill = self.sudo().with_context(
            active_test=False,
            skip_hardcoded_restrictions=True,
        )
        rows = Skill.search([
            ('source_module', '=', name),
            ('owner_id', '=', False),
        ])
        gone = Skill.browse()
        for rec in rows:
            if factory_row_on_disk(
                rec.rel_path, rec.code, rec.command,
                on_disk, disk_codes, disk_commands,
            ):
                continue
            gone |= rec
        if not gone:
            return 0
        codes = gone.mapped('code')
        gone.unlink()
        _logger.info(
            'MCP: unlinked retired factory skills of %s: %s', name, codes,
        )
        return len(codes)

    @api.model
    def unlink_named_factory_skills(self, names):
        """Unlink factory rows by code/command/rel_path. No owner.

        Used by an addon's XML seed so a ``-u`` drops product leftovers
        even when a one-shot migrate already ran.
        """
        self._require_bootstrap()
        names = [n for n in (names or []) if n]
        if not names:
            return 0
        paths = ['skills/system/%s.md' % n for n in names]
        Skill = self.sudo().with_context(
            active_test=False,
            skip_hardcoded_restrictions=True,
        )
        rows = Skill.search([
            '&',
            ('owner_id', '=', False),
            '|', '|',
            ('code', 'in', names),
            ('command', 'in', names),
            ('rel_path', 'in', paths),
        ])
        if not rows:
            return 0
        codes = rows.mapped('code')
        rows.unlink()
        _logger.info('MCP: unlinked named factory skills %s', codes)
        return len(codes)

    @api.model
    def import_from_module(self, module_name, scopes=None):
        """Seed one addon's skills on install/-u. Does not scan neighbors.

        Upserts from that module's ``ai/skills/``, then drops factory leftovers
        whose ``.md`` is gone. ``scopes`` defaults to system+custom (owner
        pack). The engine passes ``('system',)`` so it never plants ``custom/``.
        """
        ensure_ai_admin(self.env)
        name = (module_name or '').strip()
        if not name:
            raise UserError(_('Skill import requires a module name.'))
        stats = self.import_from_files(
            replace_existing=True,
            module_name=name,
            scopes=scopes,
        )
        retired = self.sudo()._unlink_retired_from_module(name)
        if isinstance(stats, dict):
            stats['retired'] = retired
        return stats

    def _after_factory_skill_import(self, stats):
        """Hook after file→DB sync. Tenant packs re-apply instance prefixes.

        ``import_from_files`` writes on-disk identity (filename + ``skill:``).
        A pack that seeds catalog/slash prefixes must rewrite its rows here
        so a ``-u`` of that pack does not leave disk codes as the live slash.
        """
        hidden = self.hide_unprefixed_slash_twins()
        if isinstance(stats, dict):
            stats['hidden_twins'] = hidden
        return stats

    @api.model
    def default_skill_codes_for_agent(self, agent_code, pull_tokens=None):
        """Shipped default skill set for an agent (pull ∪ push).

        Pull: ``ai.agent.default_skill_codes`` (codes and ``@module`` packs).
        ``@module`` includes every factory skill of that ``source_module``
        unless the skill declared exclusive ``agent_codes``. Empty
        ``agent_codes`` is included by ``@``. Push: explicit ``agent_codes``.
        ``pull_tokens`` overrides the live recipe (factory restore = seed).
        """
        codes = set()
        if not agent_code:
            return codes
        Agent = self.env['ai.agent']
        Context = self.env['ai.context']
        agent = Agent.search([('code', '=', agent_code)], limit=1)
        if pull_tokens is not None:
            pull_codes, pull_packs = pull_tokens
        else:
            pull_codes, pull_packs = (
                agent._default_skill_tokens() if agent else (set(), set())
            )
        codes |= pull_codes
        restrict_to_seed = pull_tokens is not None
        own_mods = set()
        if restrict_to_seed and agent:
            own_mods = {
                (agent.module_name or '').strip(),
                (agent.code or '').strip(),
            }
            own_mods.discard('')
        for source_mod, base in self._get_skill_source_paths():
            pack_pull = source_mod in pull_packs
            for scope in ('system', 'custom'):
                scope_dir = os.path.join(base, scope)
                if not os.path.isdir(scope_dir):
                    continue
                for filename in sorted(os.listdir(scope_dir)):
                    if not filename.endswith('.md'):
                        continue
                    try:
                        with open(os.path.join(scope_dir, filename), 'r',
                                  encoding='utf-8') as fobj:
                            meta, _body = self._skill_parse_md(fobj.read())
                    except Exception:
                        continue
                    code, _command = split_skill_identity(filename, meta)
                    if not code:
                        continue
                    exclusive = Context._explicit_agent_codes_from_metadata(
                        meta,
                    )
                    if (
                        restrict_to_seed
                        and source_mod not in pull_packs
                        and source_mod not in own_mods
                        and code not in pull_codes
                    ):
                        continue
                    if code in pull_codes:
                        codes.add(code)
                        continue
                    if pack_pull:
                        if (
                            exclusive is not None
                            and agent_code not in exclusive
                        ):
                            continue
                        codes.add(code)
                        continue
                    if exclusive and agent_code in exclusive:
                        codes.add(code)
        return codes

    @api.model
    def reload_from_server(self, replace_existing=True):
        """UI entry-point: resync skills from module files into DB, then notify.

        replace_existing controls whether code matches are overwritten (True) or
        skipped, leaving the DB rows untouched (False)."""
        ensure_ai_admin(self.env)
        stats = self.import_from_files(replace_existing=replace_existing)
        errors = stats.get('errors') or []
        _sc, _si, _st, ntype = pns_ui.derive_operation_status(
            errors,
            stats.get('created', 0) + stats.get('updated', 0),
            failed_text=_('Reload failed.'),
            warnings_text=_('Reload completed with warnings.'),
            success_text=_('Reload completed.'),
        )
        message = pns_ui.build_plain_operation_message(
            _('Reload completed'),
            [
                (_("Created"), stats.get('created', 0)),
                (_("Updated"), stats.get('updated', 0)),
                (_("Skipped (not overwritten)"), stats.get('skipped', 0)),
            ],
            errors=errors,
        )
        return pns_ui.client_notification(
            _("Reload from server"),
            message,
            notification_type=ntype if ntype != 'danger' else 'warning',
        )
