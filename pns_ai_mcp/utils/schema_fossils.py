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
    'ai_provider_usage_day',
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
LEFTOVER_COLUMNS = (
    ('ai_log', 'operation_code'),
    ('ai_agent', 'auto_link_mcp_nucleus'),
    ('ai_context', 'is_shared'),
    ('ai_skill', 'is_shared'),
    ('ai_provider', 'cost_policy'),
    ('ai_provider', 'is_on_premise'),
    ('ai_agent', 'link_show_native'),
    ('ai_agent', 'link_show_pinned'),
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
