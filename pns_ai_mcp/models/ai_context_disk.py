# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""ai.context: import contexts from the module files on disk, link them to agents, restore from the module."""

from odoo import (
    models,
    api,
    _,
)
from odoo.exceptions import UserError
from ..utils import mcp_ui as pns_ui
from ..utils import context_roles
from ..utils.import_export_guard import ensure_ai_admin
import logging

_logger = logging.getLogger(__name__)


class AIContextDisk(models.Model):
    _inherit = 'ai.context'

    def action_restore_from_module(self, replace_existing=True):
        """
        Restore ALL contexts (system and custom defaults) from module. 
        Only accessible for group_ai_admin.

        replace_existing=True: sobreescribe los contextos cuyo código coincide
        (el ``active`` de la instancia se queda). replace_existing=False: solo
        añade los que no existen. Una semilla cuyo fichero ya no está se retira
        si el escaneo de esa carpeta encontró ficheros.
        """
        # Check permissions
        if not self.env.user.has_group('pns_ai_mcp.group_ai_admin'):
            raise UserError(
                _('Only administrators can restore contexts from the module.')
            )
        
        _logger.warning("MCP: Starting manual restoration from module...")
        
        # Call the unified import method with special context to allow overwriting
        result = self.with_context(skip_hardcoded_restrictions=True)._import_all_from_module(
            replace_existing=replace_existing,
        )

        errors = result.get('errors') or []
        _sc, _si, _st, ntype = pns_ui.derive_operation_status(
            errors,
            result['imported'] + result['updated'],
            failed_text=_('Restore failed.'),
            warnings_text=_('Restore completed with warnings.'),
            success_text=_('Restore completed.'),
        )
        message = pns_ui.build_plain_operation_message(
            _('Restore completed'),
            [
                (_("Imported"), result['imported']),
                (_("Updated"), result['updated']),
                (_("Skipped (not overwritten)"), result.get('skipped', 0)),
            ],
            errors=errors,
        )
        return pns_ui.client_notification(
            _("Restore from module"),
            message,
            notification_type=ntype if ntype != 'danger' else 'warning',
        )

    @api.model
    def _get_module_path(self):
        """Legacy: returns pns_ai_mcp module path only.
        Prefer _get_context_source_paths() for multi-module scanning."""
        import os
        from odoo.modules.module import get_module_path
        module_path = get_module_path('pns_ai_mcp')
        if module_path and os.path.exists(module_path):
            return module_path
        current_file = os.path.abspath(__file__)
        return os.path.dirname(os.path.dirname(current_file))

    @api.model
    def _get_context_source_paths(self):
        """Return list of (module_name, contexts_dir) for all installed modules
        that have a contexts/ directory.

        This enables multi-module context contribution:
        - pns_ai_mcp contributes context_type=core (protocol, execution rules)
        - Any agent module can contribute its own contexts

        Returns:
            list of tuples: [(module_name, absolute_path_to_contexts_dir), ...]
        """
        from odoo.modules.module import get_module_path
        from ..utils.ai_paths import module_kind_dir
        result = []
        installed = self.env['ir.module.module'].sudo().search([
            ('state', 'in', ('installed', 'to upgrade', 'to install')),
        ])
        for mod in installed:
            mod_path = get_module_path(mod.name)
            if not mod_path:
                continue
            # Dual-path: prefer ai/contexts (PAAP umbrella), fall back to contexts.
            ctx_dir = module_kind_dir(mod_path, 'contexts')
            if ctx_dir:
                result.append((mod.name, ctx_dir))
                _logger.debug('Context source found: %s → %s', mod.name, ctx_dir)
        return result

    @staticmethod
    def _is_python_content(content):
        python_markers = ('def ', 'class ', 'import ', 'from ')
        content = content or ''
        return any(marker in content for marker in python_markers)

    @api.model
    def import_system_from_files(self):
        """
        Public method to trigger context import manually (e.g. from UI button).
        Falls back to _import_all_from_module to ensure consistent behavior.
        """
        ensure_ai_admin(self.env)
        _logger.info("MCP: import_system_from_files called via UI/Action - Triggering full module sync.")
        return self._import_all_from_module()

    @api.model
    def _invalidate_agent_caches_after_import(self):
        """Tras restore/import de contextos, vaciar cachés compiladas de agentes.

        SQL inmediato con ``FOR UPDATE SKIP LOCKED``: si el Odoo vivo (workers/
        crons) tiene filas de ``ai_agent`` bloqueadas —p. ej. durante ``t.sh -u``—
        no esperamos lock_timeout ni tumba el registry. El ``write()`` ORM
        difería el SQL al ``flush()`` de ``call_kw``, fuera de cualquier try.

        Siempre en savepoint: un ``could not serialize access`` de Postgres
        aborta la transacción actual; sin savepoint, el ``except`` solo traga
        el error Python y el ``-u`` siguiente (cron XML, etc.) muere con
        ``current transaction is aborted``.
        """
        cr = self.env.cr
        try:
            with cr.savepoint():
                cr.execute(
                    """
                    UPDATE ai_agent
                       SET cached_content = NULL,
                           cache_locale = NULL,
                           cache_context_signature = NULL,
                           write_uid = %s,
                           write_date = (now() at time zone 'UTC')
                     WHERE id IN (
                           SELECT id FROM ai_agent FOR UPDATE SKIP LOCKED
                     )
                    """,
                    [self.env.uid],
                )
                updated = cr.rowcount
            try:
                from odoo.addons.pns_ai_mcp.utils.compat import (
                    invalidate_recordset_fields,
                )
                invalidate_recordset_fields(
                    self.env['ai.agent'].sudo().search([]),
                    ['cached_content', 'cache_locale', 'cache_context_signature'],
                )
            except Exception:
                pass
            if updated is not None:
                _logger.info(
                    'MCP: agent caches invalidated after import (%s row(s))',
                    updated,
                )
        except Exception as exc:
            _logger.warning(
                'MCP: could not invalidate agent caches after import: %s', exc,
            )

    @api.model
    def _module_ships_context_code(self, module_name, code):
        """True when ``module_name`` still has a file for this context code."""
        from ..utils.context_code_scan import codes_in_contexts_dir

        if not module_name or not code:
            return False
        for source_mod, contexts_dir in self._get_context_source_paths():
            if source_mod != module_name:
                continue
            return code in codes_in_contexts_dir(contexts_dir)
        return False

    @api.model
    def _import_all_from_module(self, replace_existing=True, module_name=None,
                                core_only=False, only_codes=None):
        """Import contexts from all installed modules that ship a contexts dir.

        Scans each module's ``ai/contexts/`` directory recursively.
        Subdirectories named ``system/`` yield context_type=core contexts;
        everything else yields domain/locale contexts.

        Args:
            replace_existing: True = overwrite matching codes (upsert) when the
                              DB row has no ``owner_id`` (factory). User-owned
                              rows (``owner_id`` set) are always skipped.
                              The instance ``active`` flag is not overwritten.
                              False = additive only (no overwrite).
                              Factory rows whose file is gone are unlinked
                              after a successful scan of that module.
            module_name:      If set, only import from this specific module.
            core_only:        True = only refresh core/system contexts.
            only_codes:       Optional iterable of context codes. When set, only
                              those codes are imported/updated (no pruning).

        Returns:
            dict with keys: imported, updated, skipped, deleted, errors.
        """
        import os
        import re

        sources = self._get_context_source_paths()
        if module_name:
            sources = [(mn, cd) for mn, cd in sources if mn == module_name]
            if not sources:
                from odoo.modules.module import get_module_path
                from ..utils.ai_paths import module_kind_dir
                path = get_module_path(module_name)
                ctx_dir = module_kind_dir(path, 'contexts') if path else None
                if ctx_dir:
                    sources = [(module_name, ctx_dir)]

        total_imported = 0
        total_updated = 0
        total_skipped = 0
        total_deleted = 0
        total_errors = []

        for source_mod, contexts_dir in sources:
            _logger.info('MCP: importing contexts from module %s (%s)', source_mod, contexts_dir)
            result = self._import_contexts_from_dir(
                contexts_dir, source_mod, replace_existing,
                core_only=core_only, only_codes=only_codes,
            )
            total_imported += result['imported']
            total_updated += result['updated']
            total_skipped += result['skipped']
            total_deleted += result['deleted']
            total_errors.extend(result['errors'])

        # Legacy fallback: if no sources found via registry, try pns_ai_mcp directly
        if not sources and not module_name:
            from ..utils.ai_paths import module_kind_dir
            fallback_dir = module_kind_dir(self._get_module_path(), 'contexts')
            if fallback_dir and os.path.isdir(fallback_dir):
                _logger.warning('MCP: no modules found via registry, fallback to pns_ai_mcp')
                result = self._import_contexts_from_dir(
                    fallback_dir, 'pns_ai_mcp', replace_existing,
                    core_only=core_only, only_codes=only_codes,
                )
                total_imported += result['imported']
                total_updated += result['updated']
                total_skipped += result['skipped']
                total_deleted += result['deleted']
                total_errors.extend(result['errors'])

        _logger.info(
            'MCP: Import complete. %d imported, %d updated, %d skipped, '
            '%d deleted, %d errors (from %d modules)',
            total_imported, total_updated, total_skipped,
            total_deleted, len(total_errors), len(sources),
        )
        try:
            self._retire_generic_self_row()
        except Exception:
            _logger.warning(
                'MCP: could not retire leftover generic self rows after import',
                exc_info=True,
            )
        try:
            self._unlink_retired_engine_discovery_geo()
        except Exception:
            _logger.warning(
                'MCP: could not drop leftover engine discovery_geo rows',
                exc_info=True,
            )
        try:
            Agent = self.env['ai.agent']
            if hasattr(Agent, '_unlink_foreign_identity_packs'):
                Agent.search([])._unlink_foreign_identity_packs()
        except Exception:
            _logger.warning(
                'MCP: could not rewrite leftover identity pins after import',
                exc_info=True,
            )
        self._invalidate_agent_caches_after_import()
        return {
            'imported': total_imported,
            'updated': total_updated,
            'skipped': total_skipped,
            'deleted': total_deleted,
            'errors': total_errors,
        }

    @api.model
    def _explicit_agent_codes_from_metadata(self, metadata):
        """Exclusive ``agent_codes`` list, or None if the pack is not exclusive.

        None — no tag (own-module / default push; ``@module`` pull allowed).
        [] — ``none`` / ``catalog`` (catalog only; pull only if the code is listed).
        ['pns_ai_mcp', …] — exclusive to those agents.
        """
        metadata = metadata or {}
        raw = metadata.get('agent_codes') or metadata.get('agent_code') or ''
        if not str(raw).strip():
            return None
        normalized = str(raw).strip().lower()
        if normalized in ('none', 'false', '-', 'catalog'):
            return []
        return [c.strip() for c in str(raw).split(',') if c.strip()]

    @api.model
    def _resolve_import_agent_codes(self, metadata, source_mod, context_type='domain'):
        """Agent codes to link after import (push side of dual wire).

        Dual wire (see docs/decisions/context_code_owners.md):

        - **Push (this method):** explicit ``agent_codes`` in the pack file;
          otherwise own-module agents (``ai.agent.module_name == source_mod``);
        - **Pull:** agents whose ``default_context_codes`` list the code /
          ``@source_mod`` — applied in ``_link_context_after_import``.
          Explicit ``agent_codes`` makes ``@module`` pull exclusive.

        ``agent_codes: none`` / ``catalog`` = catalog only (no push).
        Core contexts are never linked via context_ids.
        """
        exclusive = self._explicit_agent_codes_from_metadata(metadata)
        if exclusive is not None:
            return list(exclusive)
        if context_type == 'core':
            return []
        codes = []
        # Own-module push: pack that ships the agent links its knowledge to it.
        if source_mod:
            own = self.env['ai.agent'].search([
                ('module_name', '=', source_mod),
            ])
            codes.extend(own.mapped('code'))
        if source_mod == 'pns_ai_mcp':
            if 'pns_ai_mcp' not in codes:
                codes.append('pns_ai_mcp')
        return codes

    def _pull_agent_codes_for_context(
        self, context_code, source_mod, pack_exclusive=False,
    ):
        """Agents that pull this context via default_context_codes."""
        if not context_code:
            return []
        codes = []
        for agent in self.env['ai.agent'].search([]):
            if agent.wants_context_code(
                context_code,
                source_module=source_mod,
                pack_exclusive=pack_exclusive,
            ):
                codes.append(agent.code)
        return codes

    def _link_context_after_import(self, record, push_agent_codes, source_mod=None):
        """Link context via push codes ∪ pull lists (dual wire)."""
        # ``core`` is auto-injected; ``discovery`` is engine-consumed routing —
        # neither is ever wired to an agent's context_ids.
        if not record or record.context_type in context_roles.AGENT_LINK_EXCLUDED_TYPES:
            return
        source_mod = source_mod or record.source_module
        metadata = self._extract_metadata_from_content(
            record.content or '', 'pack.xml',
        )
        pack_exclusive = self._explicit_agent_codes_from_metadata(metadata) is not None
        codes = list(push_agent_codes or [])
        for code in self._pull_agent_codes_for_context(
            record.code, source_mod, pack_exclusive=pack_exclusive,
        ):
            if code not in codes:
                codes.append(code)
        self._link_context_to_import_agents(record, codes)

    def _link_context_to_import_agents(self, record, agent_codes):
        """Wire a non-core context to the agents declared at import time."""
        if (
            not record
            or record.context_type in context_roles.AGENT_LINK_EXCLUDED_TYPES
            or not agent_codes
        ):
            return
        Agent = self.env['ai.agent']
        for code in agent_codes:
            agent = Agent.search([('code', '=', code)], limit=1)
            if agent:
                agent.context_ids = [(4, record.id)]

    @api.model
    def default_context_codes_for_agent(self, agent_code, pull_tokens=None):
        """Shipped default composition for an agent (pull ∪ push).

        Read-only scan of on-disk context files plus the agent's
        ``default_context_codes`` pull list. ``core`` contexts are excluded.
        ``pull_tokens`` overrides the live recipe (used by factory restore
        to expand only the XML seed).
        """
        import os

        from ..utils.agent_identity import is_retired_self_source_path

        codes = set()
        if not agent_code:
            return codes
        Agent = self.env['ai.agent']
        agent = Agent.search([('code', '=', agent_code)], limit=1)
        if pull_tokens is not None:
            pull_codes, pull_packs = pull_tokens
        else:
            pull_codes, pull_packs = (
                agent._default_context_tokens() if agent else (set(), set())
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
        for source_mod, contexts_dir in self._get_context_source_paths():
            if not contexts_dir or not os.path.isdir(contexts_dir):
                continue
            pack_pull = source_mod in pull_packs
            for root, _dirs, files in os.walk(contexts_dir):
                for filename in files:
                    if not filename.endswith(('.md', '.py', '.xml', '.json')):
                        continue
                    filepath = os.path.join(root, filename)
                    if not os.path.isfile(filepath):
                        continue
                    rel = os.path.relpath(filepath, contexts_dir).replace('\\', '/')
                    if is_retired_self_source_path(rel):
                        continue
                    is_system = rel.startswith('system/') or rel.startswith('core/')
                    # Discovery rows are engine-consumed routing, never part of an
                    # agent's default composition.
                    if rel.startswith('discovery/') or rel.startswith('discover/'):
                        continue
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                        if not content.strip():
                            continue
                        metadata = self._extract_metadata_from_content(content, filename)
                        code = self.generate_code_from_name(filepath)
                        if metadata.get('contexto'):
                            code = self.normalize_code(metadata['contexto'])
                        elif metadata.get('code'):
                            code = self.normalize_code(metadata['code'])
                        _cat = metadata.get('tipo') or ''
                        if _cat == context_roles.DISCOVERY:
                            continue
                        ctype = context_roles.canonical_type(
                            _cat, is_system=is_system,
                        )
                        # ``core`` + ``discovery`` are never hand-wired to agents.
                        if ctype in context_roles.AGENT_LINK_EXCLUDED_TYPES:
                            continue
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
                            exclusive = self._explicit_agent_codes_from_metadata(
                                metadata,
                            )
                            if exclusive is not None and agent_code not in exclusive:
                                continue
                            codes.add(code)
                            continue
                        agent_codes = self._resolve_import_agent_codes(
                            metadata, source_mod, context_type=ctype,
                        )
                        if agent_code in agent_codes:
                            codes.add(code)
                    except Exception:
                        _logger.warning(
                            'MCP: default-composition scan failed for %s',
                            filepath, exc_info=True,
                        )
        return codes

    def _discovery_vals_from_metadata(self, metadata):
        """Map parsed JSON short keys onto ORM discovery fields."""
        return {
            'discovery_target': metadata.get('discovery_target') or '',
            'discovery_target_kind': metadata.get('discovery_target_kind') or 'domain',
            'discovery_triggers': metadata.get('discovery_triggers') or '[]',
            'discovery_priority': metadata.get('discovery_priority') or 0,
            'discovery_soft_depends': metadata.get('discovery_soft_depends') or False,
        }

    @api.model
    def _import_contexts_from_dir(self, contexts_dir, source_mod, replace_existing=True,
                                  core_only=False, only_codes=None):
        """Import contexts from a single module's ai/contexts/ directory.

        Args:
            contexts_dir: Absolute path to the module's ai/contexts/ directory.
            source_mod: Technical name of the contributing module.
            replace_existing: True = overwrite matching. False = additive.
                              Factory rows whose file is gone are unlinked
                              after a successful scan (not if the folder
                              yielded no files).
            core_only: True = process only system/core files, skipping
                       user-editable domain/locale contexts.
            only_codes: Optional set/list of codes to import; skips prune.

        Returns:
            dict with keys: imported, updated, skipped, deleted, errors.
        """
        import os
        import re

        from ..utils.agent_identity import (
            is_retired_self_pack_code,
            is_retired_self_source_path,
        )

        imported_count = 0
        updated_count = 0
        skipped_count = 0
        errors = []
        found_codes = []
        system_codes_in_files = []
        only_codes_set = set(only_codes) if only_codes else None

        if not os.path.exists(contexts_dir):
            return {'imported': 0, 'updated': 0, 'skipped': 0, 'deleted': 0, 'errors': []}

        module_dir = os.path.dirname(contexts_dir)

        for root, dirs, files in os.walk(contexts_dir):
            for filename in files:
                if not filename.endswith(('.md', '.py', '.xml', '.json')):
                    continue

                filepath = os.path.join(root, filename)
                if not os.path.isfile(filepath):
                    continue

                rel_path_from_contexts = os.path.relpath(filepath, contexts_dir).replace('\\', '/')
                rel_path_from_module = os.path.relpath(filepath, module_dir).replace('\\', '/')

                is_system = (
                    rel_path_from_contexts.startswith('system/')
                    or rel_path_from_contexts.startswith('core/')
                )
                is_discovery = (
                    rel_path_from_contexts.startswith('discovery/')
                    or rel_path_from_contexts.startswith('discover/')
                )
                is_custom = not is_system  # Everything non-system is agent-contributed

                # core_only: refresh shipped protocol (core) contexts only,
                # leaving user-editable domain/locale contexts untouched.
                # only_codes may still target domain files explicitly.
                if core_only and not is_system and not only_codes_set:
                    continue

                try:
                    code = self.generate_code_from_name(filepath)

                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()

                    if not content.strip():
                        errors.append(f"{rel_path_from_contexts}: empty file")
                        continue

                    metadata = self._extract_metadata_from_content(content, filename)

                    if metadata.get('contexto'):
                        code = self.normalize_code(metadata['contexto'])
                    elif metadata.get('code'):
                        code = self.normalize_code(metadata['code'])
                    if is_discovery:
                        code = context_roles.canonical_discovery_code(code)

                    if only_codes_set is not None and code not in only_codes_set:
                        continue

                    found_codes.append(code)
                    if (
                        is_retired_self_pack_code(code)
                        or is_retired_self_source_path(rel_path_from_contexts)
                        or is_retired_self_source_path(rel_path_from_module)
                    ):
                        skipped_count += 1
                        _logger.info(
                            'MCP: skip retired identity pack %s (%s/%s)',
                            code, source_mod, rel_path_from_contexts,
                        )
                        continue
                    if is_system:
                        system_codes_in_files.append(code)

                    description = metadata.get('description') or f"Context imported from {source_mod}/{rel_path_from_contexts}"

                    _cat = metadata.get('tipo') or ''
                    _ctype = context_roles.canonical_type(
                        _cat,
                        discovery_folder=is_discovery,
                        is_system=is_system,
                    )
                    # Discovery rows are engine-consumed routing, not agent content.
                    if context_roles.is_discovery(_ctype):
                        agent_codes = []
                    else:
                        agent_codes = self._resolve_import_agent_codes(
                            metadata, source_mod, context_type=_ctype,
                        )
                    vals = {
                        'code': code,
                        'description': description,
                        'context_type': _ctype,
                        'content': content,
                        'rel_path': rel_path_from_module,
                        'source_module': source_mod,
                        'locale': self._infer_explicit_locale(
                            code, content, metadata,
                        ) or False,
                        'active': metadata.get('active', True) if metadata.get('active') is not None else True,
                    }

                    if metadata.get('author'):
                        vals['author'] = metadata['author']
                    if metadata.get('version'):
                        vals['version'] = metadata['version']
                    if metadata.get('date_modified'):
                        vals['date_modified'] = metadata['date_modified']

                    if context_roles.is_discovery(_ctype):
                        vals.update(self._discovery_vals_from_metadata(metadata))

                    existing = self.search([('code', '=', code)], limit=1)

                    if not existing:
                        existing_by_path = self.search([
                            ('rel_path', '=', rel_path_from_module),
                            ('context_type', '=' if is_system else '!=', 'core'),
                        ], limit=1)
                        if existing_by_path:
                            _logger.info('MCP: code rename detected for %s: %s → %s',
                                         rel_path_from_module, existing_by_path.code, code)
                            existing = existing_by_path

                    if existing:
                        if not replace_existing:
                            skipped_count += 1
                            continue
                        # User-created knowledge (owner_id set) is never overwritten
                        # by module files — factory rows have empty owner.
                        if existing.owner_id:
                            skipped_count += 1
                            _logger.info(
                                'MCP: skip factory overwrite of user-owned '
                                'context %s (owner=%s)',
                                existing.code, existing.owner_id.login,
                            )
                            continue
                        # One code → one owner. Incoming may take over only
                        # when the current owner no longer ships that code.
                        if (
                            existing.source_module
                            and existing.source_module != source_mod
                        ):
                            from ..utils.context_code_scan import (
                                factory_row_blocks_incoming,
                            )
                            owner_ships = self._module_ships_context_code(
                                existing.source_module, code,
                            )
                            if factory_row_blocks_incoming(
                                existing.source_module, source_mod, owner_ships,
                            ):
                                _logger.warning(
                                    'MCP: skip content write for context %s '
                                    '(owner=%s, attempted=%s); linking only',
                                    code, existing.source_module, source_mod,
                                )
                                self._link_context_after_import(
                                    existing, agent_codes, source_mod=source_mod,
                                )
                                skipped_count += 1
                                continue
                            _logger.info(
                                'MCP: factory context %s owner %s → %s '
                                '(previous owner no longer ships it)',
                                code, existing.source_module, source_mod,
                            )
                        if existing.code != code:
                            vals['code'] = code
                        write_vals = dict(vals)
                        write_vals.pop('active', None)
                        existing.with_context(
                            tracking_disable=True, skip_hardcoded_restrictions=True,
                        ).write(write_vals)
                        self._link_context_after_import(
                            existing, agent_codes, source_mod=source_mod,
                        )
                        updated_count += 1
                        _logger.info('MCP: updated context %s from %s/%s',
                                     code, source_mod, rel_path_from_contexts)
                    else:
                        record = self.with_context(tracking_disable=True).create(vals)
                        self._link_context_after_import(
                            record, agent_codes, source_mod=source_mod,
                        )
                        imported_count += 1
                        _logger.info('MCP: imported context %s from %s/%s',
                                     code, source_mod, rel_path_from_contexts)

                except Exception as e:
                    error_msg = f"{source_mod}/{rel_path_from_contexts}: {e}"
                    errors.append(error_msg)
                    _logger.error('MCP: error importing %s: %s', filepath, e, exc_info=True)

        deleted_count = 0
        if (
            replace_existing
            and only_codes_set is None
            and not core_only
            and found_codes
        ):
            deleted_count = self.unlink_retired_from_module(
                source_mod, found_codes=found_codes,
            )

        return {
            'imported': imported_count,
            'updated': updated_count,
            'skipped': skipped_count,
            'deleted': deleted_count,
            'errors': errors,
        }

    @api.model
    def unlink_retired_from_module(self, module_name, found_codes=None):
        """Unlink factory contexts of this addon whose file is gone.

        User-owned rows stay. Rows without ``rel_path`` stay (runtime
        discovery, not a seed). Does nothing when *found_codes* is empty
        (broken or empty scan must not wipe the catalog).
        """
        name = (module_name or '').strip()
        if not name:
            return 0
        on_disk = set(found_codes or ())
        if not on_disk:
            _logger.warning(
                'MCP: skip retired unlink for contexts of %s (no files on disk)',
                name,
            )
            return 0
        Context = self.sudo().with_context(
            active_test=False,
            skip_hardcoded_restrictions=True,
        )
        rows = Context.search([
            ('source_module', '=', name),
            ('owner_id', '=', False),
            ('rel_path', '!=', False),
        ])
        gone = Context.browse()
        for rec in rows:
            if rec.code in on_disk:
                continue
            gone |= rec
        if not gone:
            return 0
        codes = gone.mapped('code')
        gone.unlink()
        _logger.info(
            'MCP: unlinked retired factory contexts of %s: %s', name, codes,
        )
        return len(codes)

    @api.model
    def _import_system_from_files_internal(self):
        """
        Método interno que importa contextos.
        [REFACTOR CENTRALIZACIÓN]
        Anteriormente tenía su propia lógica, lo que causaba inconsistencias (casing, locales).
        Ahora delega DIRECTAMENTE en _import_all_from_module() para asegurar que
        HAYA UNA ÚNICA FORMA DE IMPORTAR, sea manual o por código.
        """
        _logger.info("MCP: _import_system_from_files_internal -> Delegando a lógica unificada _import_all_from_module")
        return self._import_all_from_module()

    @api.model
    def _import_from_files_internal(self):
        """
        Método interno que importa contextos desde archivos.
        [REFACTOR CENTRALIZACIÓN]
        Delega en _import_all_from_module.
        """
        _logger.info("MCP: _import_from_files_internal -> Delegando a lógica unificada _import_all_from_module")
        return self._import_all_from_module()
