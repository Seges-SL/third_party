# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""ai.skill: the slash command, hidden slashes, ownership, names and the invocation payload."""

import json
import logging
import re
import shlex

from odoo import api, models, _
from odoo.exceptions import UserError
from ..utils.skill_code_prefix import (
    get_skill_code_prefix,
    get_skill_command_prefix,
    instance_identity,
    invoke_lookup_tokens,
    is_auto_prefixed_code,
    leftover_twin_action,
    reserved_slash_commands,
    slash_slug,
    stem_for_reapply,
    uniquify_catalog_code,
    unprefixed_twin_stems,
)

from .ai_skill import (
    ICP_SKILLS_SLASH_HIDDEN,
)

_logger = logging.getLogger(__name__)


class AISkillSlash(models.Model):
    _inherit = 'ai.skill'

    @api.model
    def _slash_hidden_codes(self):
        """Catalog codes hidden from the slash menu (ICP source of truth)."""
        ICP = self.env['ir.config_parameter'].sudo()
        raw = ICP.get_param(ICP_SKILLS_SLASH_HIDDEN, '[]') or '[]'
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            data = []
        if not isinstance(data, list):
            return set()
        return {str(x).strip() for x in data if str(x).strip()}

    @api.model
    def _set_slash_hidden_codes(self, codes):
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param(
            ICP_SKILLS_SLASH_HIDDEN,
            json.dumps(sorted(set(codes)), ensure_ascii=False),
        )

    def _sync_slash_hidden_icp(self):
        """Mirror show_in_slash → ICP for the current records' codes."""
        hidden = self._slash_hidden_codes()
        for rec in self:
            code = (rec.code or '').strip()
            if not code:
                continue
            if rec.show_in_slash:
                hidden.discard(code)
            else:
                hidden.add(code)
        self._set_slash_hidden_codes(hidden)

    def _apply_slash_hidden_from_icp(self):
        """Force show_in_slash=False when the skill code is listed in ICP."""
        hidden = self._slash_hidden_codes()
        if not hidden:
            return
        to_hide = self.filtered(
            lambda s: (
                ((s.code or '').strip() in hidden
                 or (s.command or '').strip() in hidden)
                and s.show_in_slash
            ),
        )
        if to_hide:
            to_hide.with_context(skip_slash_icp_sync=True).write({
                'show_in_slash': False,
            })

    @api.model
    def _find_by_invoke_token(self, token):
        tokens = invoke_lookup_tokens(
            token,
            get_skill_code_prefix(self.env),
            get_skill_command_prefix(self.env),
        )
        if not tokens:
            return self.browse()
        conds = []
        for tok in tokens:
            conds.append(('command', '=', tok))
            conds.append(('code', '=', tok))
        domain = conds if len(conds) == 1 else (['|'] * (len(conds) - 1) + conds)
        return self.search(domain, limit=1)

    @api.model
    def _find_invoke_token_on_instance(self, token):
        """Same lookup as ``_find_by_invoke_token``, ignoring ownership ACL."""
        return self.sudo()._find_by_invoke_token(token)

    def _slash_in_use_holder(self, skill):
        """Who holds a slash: person name, or the factory catalog."""
        owner = skill.sudo().owner_id
        if owner:
            return owner.name or owner.display_name
        return _('the catalog')

    def _raise_slash_in_use(self, command, skill):
        raise UserError(_(
            'The slash "/%s" is already in use by %s. Choose another name.'
        ) % (command, self._slash_in_use_holder(skill)))

    @api.model
    def _owned_mutable_skill(self, token):
        """Resolve a skill the current Writer may delete or rename."""
        self._require_skill_author()
        skill = self._find_by_invoke_token(token)
        if not skill:
            raise UserError(_('There is no skill named "%s".') % token)
        if skill.is_system:
            raise UserError(_(
                'System skills cannot be changed from the chat.'
            ))
        if not skill.owner_id or skill.owner_id.id != self.env.uid:
            raise UserError(_('You can only change skills you created.'))
        return skill

    def _owned_extra_skills(self):
        """Skills the current Writer created (not system / factory)."""
        return self.search([
            ('owner_id', '=', self.env.uid),
            ('is_system', '=', False),
        ])

    def _skill_matches_invoke_or_name(self, skill, token, lookup_tokens):
        code_prefix = get_skill_code_prefix(self.env)
        command_prefix = get_skill_command_prefix(self.env)
        skill_tokens = set()
        cmd = (skill.command or '').strip()
        code = (skill.code or '').strip()
        if cmd:
            skill_tokens.update(invoke_lookup_tokens(
                cmd, code_prefix, command_prefix,
            ))
        if code:
            skill_tokens.update(invoke_lookup_tokens(
                code, code_prefix, command_prefix,
            ))
        if skill_tokens & set(lookup_tokens):
            return True
        needle = (token or '').strip().lower().lstrip('/')
        name = (skill.name or '').strip().lower()
        return bool(needle and needle in name)

    @api.model
    def search_owned_for_token(self, token):
        """Owned extras matching stem, prefixed slash, code, or name."""
        self._require_skill_author()
        owned = self._owned_extra_skills()
        needle = (token or '').strip()
        if not needle:
            return owned
        lookup = invoke_lookup_tokens(
            needle,
            get_skill_code_prefix(self.env),
            get_skill_command_prefix(self.env),
        )
        hits = self.browse()
        for skill in owned:
            if self._skill_matches_invoke_or_name(skill, needle, lookup):
                hits |= skill
        return hits

    @api.model
    def resolve_owned_for_params(self, token):
        """``(recordset, 'one'|'picks')``. Raises if the token is not yours."""
        self._require_skill_author()
        needle = (token or '').strip()
        if not needle:
            return self._owned_extra_skills(), 'picks'
        hits = self.search_owned_for_token(needle)
        if len(hits) > 1:
            return hits, 'picks'
        if len(hits) == 1:
            return hits, 'one'
        other = self._find_invoke_token_on_instance(needle)
        if other:
            if other.is_system:
                raise UserError(_(
                    'System skills cannot be changed from the chat.'
                ))
            raise UserError(_('You can only change skills you created.'))
        raise UserError(_('There is no skill named "%s".') % needle)

    @api.model
    def owned_skill_picks(self, skills):
        rows = []
        for rec in skills:
            slash = ''
            if hasattr(rec, 'invoke_code'):
                slash = (rec.invoke_code() or '').strip()
            if not slash:
                slash = (rec.code or '').strip()
            if not slash:
                continue
            rows.append({
                'code': slash,
                'name': (rec.name or '').strip() or slash,
            })
        rows.sort(key=lambda r: (r['code'] or '').casefold())
        return rows

    @api.model
    def resolve_capture_identity(self, raw):
        """Identity for ``/create-skill``: free slash or the caller's skill.

        Returns ``(code, command, existing)``. ``existing`` is empty when
        the slash is free. A factory, system, or other-owner clash raises
        the same errors as delete/rename.
        """
        code_prefix = get_skill_code_prefix(self.env)
        command_prefix = get_skill_command_prefix(self.env)
        slug = slash_slug(raw, default='')
        if not slug:
            raise UserError(_(
                'Enter a valid skill name (letters, numbers, hyphens).'
            ))
        code, command = instance_identity(slug, code_prefix, command_prefix)
        if command in reserved_slash_commands():
            raise UserError(_(
                'The slash "/%s" is reserved. Choose another name.'
            ) % command)
        existing = self._find_invoke_token_on_instance(command)
        if not existing:
            return code, command, existing
        if existing.owner_id and existing.owner_id.id == self.env.uid:
            owned = self._owned_mutable_skill(command)
            return owned.code, owned.command or command, owned
        self._raise_slash_in_use(command, existing)

    @api.model
    def allocate_instance_identity(self, raw, exclude_id=None):
        """Catalog ``code`` (snake) + ``command`` (kebab) for a user skill."""
        code_prefix = get_skill_code_prefix(self.env)
        command_prefix = get_skill_command_prefix(self.env)
        slug = slash_slug(raw, default='')
        if not slug:
            raise UserError(_(
                'Enter a valid skill name (letters, numbers, hyphens).'
            ))
        code, command = instance_identity(slug, code_prefix, command_prefix)
        if command in reserved_slash_commands():
            raise UserError(_(
                'The slash "/%s" is reserved. Choose another name.'
            ) % command)
        taken_domain = [('code', '=like', code + '%')]
        if exclude_id:
            taken_domain = [('id', '!=', exclude_id)] + taken_domain
        taken = set(self.sudo().search(taken_domain).mapped('code'))
        code = uniquify_catalog_code(code, taken)
        clash = self.sudo().search([
            ('id', '!=', exclude_id or 0),
            '|', '|',
            ('command', '=', command),
            ('code', '=', command),
            ('command', '=', command.replace('-', '_')),
        ], limit=1)
        if clash:
            self._raise_slash_in_use(command, clash)
        return code, command

    @api.model
    def reapply_source_module_prefixes(
        self, source_module, old_code_prefixes=(), old_command_prefixes=(),
    ):
        """Rewrite pack skills to the current instance prefixes.

        ``source_module`` selects the rows. ``old_*_prefixes`` are stripped
        before the current ICP prefixes are applied. Does not touch
        user-owned skills. Does not steal a slash from another pack or a
        builtin. Returns ``{updated, skipped, errors}``.
        """
        self._require_bootstrap()
        source_module = (source_module or '').strip()
        stats = {'updated': 0, 'skipped': 0, 'errors': []}
        if not source_module:
            return stats
        code_pfx = get_skill_code_prefix(self.env)
        cmd_pfx = get_skill_command_prefix(self.env)
        code_olds = list(old_code_prefixes or ())
        cmd_olds = list(old_command_prefixes or ())
        if code_pfx:
            code_olds.append(code_pfx)
        if cmd_pfx:
            cmd_olds.append(cmd_pfx)
        reserved = set(reserved_slash_commands())
        rows = self.sudo().search([
            ('source_module', '=', source_module),
            ('owner_id', '=', False),
        ])
        pack_ids = set(rows.ids)
        taken_codes = set(self.search([]).mapped('code'))
        for skill in rows:
            stem = stem_for_reapply(
                skill.code, skill.command, code_olds, cmd_olds,
            )
            if not stem:
                stats['skipped'] += 1
                continue
            new_code, new_command = instance_identity(
                stem, code_pfx, cmd_pfx,
            )
            if (
                new_code == (skill.code or '')
                and (new_command or '') == (skill.command or '')
            ):
                stats['skipped'] += 1
                continue
            if new_command in reserved:
                stats['errors'].append(
                    '/%s is reserved (%s)' % (new_command, skill.code)
                )
                continue
            clash = self.search([
                ('id', 'not in', list(pack_ids) or [0]),
                '|', '|',
                ('command', '=', new_command),
                ('code', '=', new_command),
                ('command', '=', new_command.replace('-', '_')),
            ], limit=1)
            if clash:
                stats['errors'].append(
                    '/%s is used by %s' % (
                        new_command, clash.invoke_code() or clash.code,
                    )
                )
                continue
            others = (taken_codes - {skill.code}) | {
                r.code for r in rows if r.id != skill.id
            }
            new_code = uniquify_catalog_code(new_code, others)
            try:
                skill.with_context(skip_hardcoded_restrictions=True).write({
                    'code': new_code,
                    'command': new_command,
                })
            except Exception as exc:
                stats['errors'].append('%s: %s' % (skill.code, exc))
                continue
            taken_codes.discard(skill.code)
            taken_codes.add(new_code)
            stats['updated'] += 1
        stats['hidden_twins'] = self.hide_unprefixed_slash_twins()
        return stats

    @api.model
    def hide_unprefixed_slash_twins(self):
        """Delete leftover slashes that duplicate a prefixed factory command.

        Instance prefix + factory ``/<prefix><stem>`` → unlink ``/<stem>``
        (user, orphan, factory or system). No archive. Product slashes that
        are not a stem of a prefixed factory row stay.
        """
        self._require_bootstrap()
        pfx = get_skill_command_prefix(self.env)
        if not pfx:
            return 0
        Skill = self.sudo().with_context(
            active_test=False,
            skip_hardcoded_restrictions=True,
        )
        factory = Skill.search([
            ('source_module', '!=', False),
            ('owner_id', '=', False),
        ])
        factory_cmds = [s.command or s.code for s in factory]
        if not unprefixed_twin_stems(factory_cmds, pfx):
            return 0
        on_disk = self._factory_skill_rel_paths_on_disk()
        to_unlink = Skill.browse()
        for rec in Skill.search([]):
            is_factory = bool(
                not rec.owner_id and (rec.source_module or rec.is_system)
            )
            action = leftover_twin_action(
                rec.invoke_code(), factory_cmds, pfx,
                rec.rel_path or '', on_disk, is_factory,
            )
            if action == 'unlink':
                to_unlink |= rec
        if not to_unlink:
            return 0
        _logger.info(
            'MCP: unlink unused unprefixed slash twins %s',
            to_unlink.mapped('code'),
        )
        n = len(to_unlink)
        to_unlink.unlink()
        return n

    @api.model
    def action_delete_owned(self, token):
        skill = self._owned_mutable_skill(token)
        name = skill.invoke_code() or skill.code
        skill.unlink()
        return {'deleted': name}

    @api.model
    def action_rename_owned(self, old_token, new_token):
        skill = self._owned_mutable_skill(old_token)
        code_prefix = get_skill_code_prefix(self.env)
        command_prefix = get_skill_command_prefix(self.env)
        new_slash = slash_slug(new_token, default='')
        if not new_slash:
            raise UserError(_(
                'Enter a valid new skill name (letters, numbers, hyphens).'
            ))
        old_slash = skill.invoke_code() or skill.code
        if is_auto_prefixed_code(
            skill.code, old_slash, code_prefix, command_prefix,
        ):
            code, command = self.allocate_instance_identity(
                new_slash, exclude_id=skill.id,
            )
        else:
            command = new_slash
            code = skill.code
            clash = self.sudo().search([
                ('id', '!=', skill.id),
                '|', '|',
                ('command', '=', command),
                ('code', '=', command),
                ('command', '=', command.replace('-', '_')),
            ], limit=1)
            if clash:
                self._raise_slash_in_use(command, clash)
        skill.write({
            'code': code,
            'command': command,
        })
        return {
            'old': old_token,
            'new': skill.invoke_code() or skill.code,
        }

    def _arg_hint_text(self):
        """Argument placeholder for the `/skill` input.

        Prefers the authored ``arg_hint`` (a real usage example). If missing,
        derives a discreet hint from the keys declared in ``param_schema``
        (names only, e.g. ``clave1=… clave2=…``). Never invents values.
        """
        self.ensure_one()
        hint = (self.arg_hint or '').strip()
        if hint:
            return hint
        schema_txt = (self.param_schema or '').strip()
        if schema_txt:
            try:
                schema = json.loads(schema_txt)
            except Exception:
                schema = None
            if isinstance(schema, dict) and schema:
                return ' '.join('%s=…' % k for k in schema.keys())
        return ''

    @staticmethod
    def _substitute_arguments(text, arguments):
        """Replace $ARGUMENTS / $0 / $1... placeholders (Claude-style)."""
        arguments = arguments or ''
        try:
            parts = shlex.split(arguments)
        except ValueError:
            parts = arguments.split()

        def _positional(match):
            idx = int(match.group(1))
            return parts[idx] if idx < len(parts) else ''

        result = re.sub(r'\$(\d+)', _positional, text)
        result = result.replace('$ARGUMENTS', arguments)
        return result

    def build_invocation_payload(self, user_locale=None, arguments=''):
        """Prompt text to inject when the skill is invoked via /<code> [args].

        Substitutes $ARGUMENTS/$N when present; otherwise appends them (like
        Claude Code) so the model always sees what the user typed.
        """
        self.ensure_one()
        text = self.build_prompt_payload(user_locale=user_locale)['text']
        arguments = (arguments or '').strip()
        if '$ARGUMENTS' in text or re.search(r'\$\d', text):
            text = self._substitute_arguments(text, arguments)
        elif arguments:
            text += '\n\nARGUMENTS: %s' % arguments
        return text
