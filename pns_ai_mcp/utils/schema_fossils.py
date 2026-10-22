# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Named leftover tables after TransientModel _name changes.

Odoo 14 never runs ``migrations/3.1.*`` leftovers: its convert_version
treats a three-part module version (``3.1.555``) as already including the
server series, then compares it to the stored ``14.0.3.1.555`` and skips
the script. Odoo 19 prefixes ``3.1.*`` → ``19.0.3.1.*`` and those leftovers
do run. Drop these names from ``ai.schema.fossil.init`` on every ``-u``.

Do not add ``ai_safe_choice`` or ``ai_change_journal``.
"""

from .engine_params import PREVIOUS_KEYS

FOSSIL_TABLES = (
    'ai_agent_pns_ai_mcp_artifact_bundle_export_wizard_rel',
    'ai_api_server_pns_ai_mcp_artifact_bundle_export_wizard_rel',
    'ai_context_pns_ai_mcp_artifact_bundle_export_wizard_rel',
    'ai_mcp_user_pns_ai_mcp_artifact_bundle_export_wizard_rel',
    'ai_provider_pns_ai_mcp_artifact_bundle_export_wizard_rel',
    'ai_skill_pns_ai_mcp_artifact_bundle_export_wizard_rel',
    'ai_url_whitelist_pns_ai_mcp_artifact_bundle_export_wizard_rel',
    'ai_relaxaicode_recipe',
    'pns_ai_mcp_relaxaicode_library',
    'pns_ai_mcp_relaxaicode_raw_result',
    'pns_ai_mcp_skill_capture_wizard',
    # Not 'ai_provider_usage_day': its daily totals are history. The table
    # stays until a person moves or drops it (Seges PNS-87).
)

PROTECTED_TABLES = (
    'ai_safe_choice',
    'ai_change_journal',
)

# One-shot -u: column painter → compose; old selection keys rewritten then gone.
COMPOSE_VALUE_TABLES = ('ai_provider', 'ai_skill')
COMPOSE_VALUE_REMAP = (
    ('painter-local', 'compose-agent'),
    ('painter-free', 'compose-model'),
    ('compose-chatboo', 'compose-agent'),
)

# ORM-removed columns that may linger when O14 skips migrations/3.1.*.
# Not ('ai_log', 'agent_id'): the agent code is history on old rows and
# stays in the column until a person drops it (Seges PNS-87).
LEFTOVER_COLUMNS = (
    ('ai_log', 'operation_code'),
    ('ai_agent', 'auto_link_mcp_nucleus'),
    ('ai_context', 'is_shared'),
    ('ai_skill', 'is_shared'),
    ('ai_provider', 'cost_policy'),
    ('ai_provider', 'is_on_premise'),
    ('ai_agent', 'link_show_native'),
    ('ai_agent', 'link_show_pinned'),
    # The temporary key PIN lived on the user until 3.1.838. It is now minted
    # by the browser tab holding the key list and never reaches the database.
    ('ai_mcp_user', 'key_pin'),
    ('ai_mcp_user', 'key_pin_used'),
    ('ai_mcp_user', 'key_pin_killed'),
)


# xmlids renamed when the models went from mcp_* to ai_* (3.1.519). Odoo 14
# never runs that pre-migrate, so the rename runs here on every -u: the row
# keeps its id, and a rule a person customised keeps the customisation.
XMLID_RENAMES = (
    ('mcp_log_user_rule', 'ai_log_user_rule'),
    ('mcp_log_admin_rule', 'ai_log_admin_rule'),
    ('menu_mcp_logs', 'menu_ai_log'),
    ('menu_mcp_logs_admin', 'menu_ai_log_admin'),
    ('action_mcp_logs', 'action_ai_log'),
    ('action_mcp_logs_technical', 'action_ai_log_technical'),
    ('action_mcp_logs_delete_menu_window', 'action_ai_log_delete_menu_window'),
    ('view_mcp_log_tree_simple', 'view_ai_log_tree_simple'),
    ('view_mcp_log_tree', 'view_ai_log_tree'),
    ('view_mcp_log_form', 'view_ai_log_form'),
    ('view_mcp_log_search', 'view_ai_log_search'),
    ('access_mcp_log_user', 'access_ai_log_user'),
    ('access_mcp_log_admin', 'access_ai_log_admin'),
    ('menu_mcp_contexts', 'menu_ai_context'),
    ('menu_mcp_contexts_writer', 'menu_ai_context_writer'),
    ('action_mcp_contexts', 'action_ai_context'),
    ('action_mcp_contexts_writer', 'action_ai_context_writer'),
    ('view_mcp_context_tree', 'view_ai_context_tree'),
    ('view_mcp_context_search', 'view_ai_context_search'),
    ('view_mcp_context_form', 'view_ai_context_form'),
    ('access_mcp_context_user', 'access_ai_context_user'),
    ('access_mcp_context_writer', 'access_ai_context_writer'),
    ('menu_mcp_change_journal', 'menu_ai_change_journal'),
    ('action_mcp_change_journal', 'action_ai_change_journal'),
    ('view_mcp_change_journal_search', 'view_ai_change_journal_search'),
    ('view_mcp_change_journal_tree', 'view_ai_change_journal_tree'),
    ('view_mcp_change_journal_form', 'view_ai_change_journal_form'),
)


def rename_leftover_xmlids(cr):
    """Rename ``mcp_*`` xmlids to ``ai_*`` in place. Idempotent."""
    for old, new in XMLID_RENAMES:
        cr.execute(
            "SELECT id FROM ir_model_data "
            "WHERE module = 'pns_ai_mcp' AND name = %s",
            (new,),
        )
        if cr.fetchone():
            continue
        cr.execute(
            "UPDATE ir_model_data SET name = %s "
            "WHERE module = 'pns_ai_mcp' AND name = %s",
            (new, old),
        )


def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def promote_compose_column(cr):
    """Move leftover painter column/values onto compose, then drop painter."""
    for table in COMPOSE_VALUE_TABLES:
        has_painter = _column_exists(cr, table, 'painter')
        has_compose = _column_exists(cr, table, 'compose')
        if has_painter and not has_compose:
            cr.execute(
                'ALTER TABLE "%s" RENAME COLUMN painter TO compose' % table
            )
            has_painter = False
            has_compose = True
        if has_painter and has_compose:
            cr.execute(
                'UPDATE "%s" SET compose = painter '
                'WHERE compose IS NULL AND painter IS NOT NULL' % table
            )
            cr.execute('ALTER TABLE "%s" DROP COLUMN painter' % table)
            has_painter = False
        if not has_compose:
            continue
        for old, new in COMPOSE_VALUE_REMAP:
            cr.execute(
                'UPDATE "%s" SET compose = %%s WHERE compose = %%s' % table,
                (new, old),
            )


def _promote_char_column(cr, table, old_col, new_col):
    """Rename or copy a char column (O14 skips migrations/3.1.*)."""
    has_old = _column_exists(cr, table, old_col)
    if not has_old:
        return
    has_new = _column_exists(cr, table, new_col)
    if not has_new:
        cr.execute(
            'ALTER TABLE "%s" RENAME COLUMN "%s" TO "%s"'
            % (table, old_col, new_col)
        )
        return
    cr.execute(
        'UPDATE "%s" SET "%s" = "%s" '
        'WHERE ("%s" IS NULL OR "%s" = \'\') '
        'AND "%s" IS NOT NULL AND "%s" != \'\'' % (
            table, new_col, old_col, new_col, new_col, old_col, old_col,
        )
    )
    cr.execute('ALTER TABLE "%s" DROP COLUMN "%s"' % (table, old_col))


def _promote_int_column(cr, table, old_col, new_col):
    """Rename or copy an integer column (O14 skips migrations/3.1.*)."""
    has_old = _column_exists(cr, table, old_col)
    if not has_old:
        return
    has_new = _column_exists(cr, table, new_col)
    if not has_new:
        cr.execute(
            'ALTER TABLE "%s" RENAME COLUMN "%s" TO "%s"'
            % (table, old_col, new_col)
        )
        return
    cr.execute(
        'UPDATE "%s" SET "%s" = "%s" '
        'WHERE "%s" IS DISTINCT FROM "%s"' % (
            table, new_col, old_col, old_col, new_col,
        )
    )
    cr.execute('ALTER TABLE "%s" DROP COLUMN "%s"' % (table, old_col))


def promote_turn_columns(cr):
    """correlation_id/step_seq -> turn/turn_step on log, journal, safe operation."""
    _promote_char_column(cr, 'ai_log', 'correlation_id', 'turn')
    _promote_int_column(cr, 'ai_log', 'step_seq', 'turn_step')
    _promote_char_column(cr, 'ai_change_journal', 'correlation_id', 'turn')
    _promote_int_column(cr, 'ai_change_journal', 'step_seq', 'turn_step')
    _promote_char_column(cr, 'ai_safe_operation', 'correlation_id', 'turn')


def _drop_column_if_exists(cr, table, column):
    if not _column_exists(cr, table, column):
        return
    cr.execute('ALTER TABLE "%s" DROP COLUMN "%s"' % (table, column))


def promote_decision_provider(cr):
    """protocol decision → systemone + Decision tick; decision_model → model_id.

    The old text column won over ``model_id`` on the call, so its model is
    kept as the selected one before the column goes. ``fit_decision`` may not
    be created yet when this runs; the ORM keeps the column it finds.
    """
    if not _column_exists(cr, 'ai_provider', 'protocol'):
        return
    cr.execute('ALTER TABLE ai_provider ADD COLUMN IF NOT EXISTS fit_decision boolean')
    cr.execute(
        "UPDATE ai_provider SET protocol = 'systemone', fit_decision = true "
        "WHERE protocol = 'decision'"
    )
    if not _column_exists(cr, 'ai_provider', 'decision_model'):
        return
    cr.execute(
        "SELECT p.id, TRIM(p.decision_model) FROM ai_provider p "
        "LEFT JOIN ai_provider_model m ON m.id = p.model_id "
        "WHERE COALESCE(TRIM(p.decision_model), '') != '' "
        "AND m.name IS DISTINCT FROM TRIM(p.decision_model)"
    )
    for provider_id, name in cr.fetchall():
        cr.execute(
            "SELECT id FROM ai_provider_model "
            "WHERE provider_id = %s AND name = %s ORDER BY id LIMIT 1",
            (provider_id, name),
        )
        row = cr.fetchone()
        if row:
            model_id = row[0]
        else:
            cr.execute(
                "INSERT INTO ai_provider_model "
                "(name, provider_id, create_date, write_date) "
                "VALUES (%s, %s, NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC') "
                "RETURNING id",
                (name, provider_id),
            )
            model_id = cr.fetchone()[0]
        cr.execute(
            "UPDATE ai_provider SET model_id = %s, model_name = %s WHERE id = %s",
            (model_id, name, provider_id),
        )
    _drop_column_if_exists(cr, 'ai_provider', 'decision_model')


def drop_leftover_columns(cr):
    """Drop ORM-removed columns (O19 leftovers 3.1.291 / 3.1.370 / 3.1.642)."""
    for table, column in LEFTOVER_COLUMNS:
        _drop_column_if_exists(cr, table, column)


def promote_engine_params(cr):
    """Move the engine's system parameters to their ``pns_ai.*`` names.

    A value already stored under the new key wins; the old row goes. The
    renamed row loses the external id of the module that seeded it, so
    uninstalling that module does not take the engine's setting with it.
    """
    for old_key, new_key in PREVIOUS_KEYS:
        cr.execute(
            'SELECT id FROM ir_config_parameter WHERE key = %s', (old_key,),
        )
        row = cr.fetchone()
        if not row:
            continue
        param_id = row[0]
        cr.execute(
            "DELETE FROM ir_model_data "
            "WHERE model = 'ir.config_parameter' AND res_id = %s",
            (param_id,),
        )
        cr.execute(
            'SELECT 1 FROM ir_config_parameter WHERE key = %s', (new_key,),
        )
        if cr.fetchone():
            cr.execute(
                'DELETE FROM ir_config_parameter WHERE id = %s', (param_id,),
            )
        else:
            cr.execute(
                'UPDATE ir_config_parameter SET key = %s WHERE id = %s',
                (new_key, param_id),
            )
