# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
""" /create-skill replaces an owned slash; factory/system/other stay blocked. """
import json
import uuid

from odoo.exceptions import UserError
from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.tests._helpers import create_test_user, ensure_test_agents
from odoo.addons.pns_ai_mcp.utils.skill_code_prefix import (
    DEFAULT_SKILL_CODE_PREFIX,
    DEFAULT_SKILL_COMMAND_PREFIX,
    ICP_SKILL_CODE_PREFIX,
    ICP_SKILL_COMMAND_PREFIX,
)
from odoo.addons.pns_ai_mcp.utils.compat import invalidate_recordset_fields


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestSkillCaptureReplace(TransactionCase):

    def setUp(self):
        super().setUp()
        # The instance may carry its own slash prefixes and language; the
        # tests name skills and read messages as a clean database does.
        self.env = self.env(context=dict(self.env.context, lang='en_US'))
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param(ICP_SKILL_CODE_PREFIX, DEFAULT_SKILL_CODE_PREFIX)
        ICP.set_param(ICP_SKILL_COMMAND_PREFIX, DEFAULT_SKILL_COMMAND_PREFIX)
        ensure_test_agents(self.env)
        self.writer_group = self.env.ref('pns_ai_mcp.group_ai_writer')
        writers = [self.env.ref('base.group_user').id, self.writer_group.id]
        self.user_a = create_test_user(self.env, prefix='pns_capture_a', groups=writers)
        self.user_b = create_test_user(self.env, prefix='pns_capture_b', groups=writers)
        self._uid = uuid.uuid4().hex[:8]

    def _slash(self, stem):
        return '%s-%s' % (stem, self._uid)

    def _create_owned(self, env, stem, **extra):
        command = self._slash(stem)
        vals = {
            'code': command.replace('-', '_'),
            'command': command,
            'name': command,
            'description': command,
            'content': 'old procedure',
            'code_body': 'result = {"formatted_text": "<p>ok</p>", "__return_direct__": True}',
        }
        vals.update(extra)
        return env['ai.skill'].create(vals)

    def _code_reads(self, *keys):
        lines = []
        for key in keys:
            lines.extend([
                'try:',
                '    %s = %s' % (key, key),
                'except NameError:',
                '    %s = None' % key,
            ])
        lines.append('result = {"formatted_text": "<p>ok</p>", "__return_direct__": True}')
        return '\n'.join(lines) + '\n'

    def test_resolve_owned_slash_returns_existing(self):
        skill = self._create_owned(
            self.env(user=self.user_a), 'mine',
            owner_id=self.user_a.id,
        )
        Skill = self.env['ai.skill'].with_user(self.user_a)
        code, command, existing = Skill.resolve_capture_identity(skill.command)
        self.assertEqual(existing, skill)
        self.assertEqual(command, skill.command)
        self.assertEqual(code, skill.code)

    def test_resolve_free_slash_has_no_existing(self):
        Skill = self.env['ai.skill'].with_user(self.user_a)
        token = self._slash('free')
        _code, command, existing = Skill.resolve_capture_identity(token)
        self.assertFalse(existing)
        self.assertTrue(command)

    def test_resolve_system_slash_is_blocked(self):
        skill = self._create_owned(
            self.env, 'sys', is_system=True,
        )
        Skill = self.env['ai.skill'].with_user(self.user_a)
        with self.assertRaises(UserError):
            Skill.resolve_capture_identity(skill.command)

    def test_resolve_factory_slash_is_blocked(self):
        skill = self._create_owned(
            self.env, 'factory', source_module='pns_ai_mcp',
        )
        Skill = self.env['ai.skill'].with_user(self.user_a)
        with self.assertRaises(UserError) as err:
            Skill.resolve_capture_identity(skill.command)
        self.assertIn('already in use by', str(err.exception))
        self.assertIn('the catalog', str(err.exception))

    def test_resolve_other_owner_is_blocked(self):
        skill = self._create_owned(
            self.env(user=self.user_a), 'other',
            owner_id=self.user_a.id,
        )
        Skill = self.env['ai.skill'].with_user(self.user_b)
        with self.assertRaises(UserError) as err:
            Skill.resolve_capture_identity(skill.command)
        msg = str(err.exception)
        self.assertIn('already in use by', msg)
        self.assertIn(self.user_a.name, msg)
        self.assertNotIn('old procedure', msg)

    def test_allocate_other_owner_names_holder(self):
        skill = self._create_owned(
            self.env(user=self.user_a), 'alloc',
            owner_id=self.user_a.id,
        )
        Skill = self.env['ai.skill'].with_user(self.user_b)
        with self.assertRaises(UserError) as err:
            Skill.allocate_instance_identity(skill.command)
        msg = str(err.exception)
        self.assertIn('already in use by', msg)
        self.assertIn(self.user_a.name, msg)

    def test_wizard_turn_chip_is_not_a_param_row(self):
        Wiz = self.env['ai.skill.capture.wizard']
        self.assertEqual(Wiz._rows_from_schema_or_prose('', 'AZ3C'), [])
        self.assertEqual(Wiz._rows_from_schema_or_prose('', 'AZ3C-2'), [])
        rows = Wiz._rows_from_schema_or_prose('', 'AZ3C cities and dates')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['desc'], 'cities and dates')
        self.assertNotIn('AZ3C', rows[0]['label'])

    def test_wizard_requires_skill_name(self):
        wiz = self.env['ai.skill.capture.wizard'].with_user(
            self.user_a,
        ).create({
            'skill_code': self._slash('noname'),
            'skill_name': '',
            'description': 'help',
            'procedure': 'proc',
            'code_body': 'result = {"formatted_text": "<p>ok</p>", "__return_direct__": True}',
            'from_chat': True,
        })
        with self.assertRaises(UserError) as err:
            wiz.action_create_draft()
        self.assertIn('name', str(err.exception).lower())

    def test_wizard_replaces_owned_body(self):
        skill = self._create_owned(
            self.env(user=self.user_a), 'wiz',
            owner_id=self.user_a.id,
        )
        wiz = self.env['ai.skill.capture.wizard'].with_user(
            self.user_a,
        ).create({
            'skill_code': skill.command,
            'skill_name': 'Replaced',
            'description': 'new hint',
            'procedure': 'new procedure',
            'code_body': 'result = {"formatted_text": "<p>99</p>", "__return_direct__": True}',
            'existing_skill_id': skill.id,
            'from_chat': True,
        })
        wiz.action_create_draft()
        invalidate_recordset_fields(skill, None)
        self.assertEqual(skill.code_body, 'result = {"formatted_text": "<p>99</p>", "__return_direct__": True}')
        self.assertEqual(skill.content, 'new procedure')
        self.assertEqual(skill.name, 'Replaced')
        self.assertEqual(skill.owner_id, self.user_a)
        self.assertEqual(skill.command, self._slash('wiz'))
        self.assertFalse(skill.is_system)

    def test_wizard_infers_schema_from_nameerror_globals(self):
        skill = self._create_owned(
            self.env(user=self.user_a), 'infer',
            owner_id=self.user_a.id,
        )
        code = (
            'try:\n'
            '    periodo = periodo\n'
            'except NameError:\n'
            '    periodo = None\n'
            'result = {"formatted_text": "<p>ok</p>", "__return_direct__": True}\n'
        )
        wiz = self.env['ai.skill.capture.wizard'].with_user(
            self.user_a,
        ).create({
            'skill_code': skill.command,
            'skill_name': 'Inferred',
            'description': 'new hint',
            'procedure': 'new procedure',
            'code_body': code,
            'existing_skill_id': skill.id,
            'from_chat': True,
        })
        wiz.action_create_draft()
        invalidate_recordset_fields(skill, None)
        schema = json.loads(skill.param_schema)
        self.assertEqual(list(schema), ['periodo'])
        self.assertIn('periodo=', skill.arg_hint)

    def test_wizard_keeps_authored_schema(self):
        skill = self._create_owned(
            self.env(user=self.user_a), 'keep',
            owner_id=self.user_a.id,
        )
        authored = '{"codes":{"type":"string","desc":"CSV"}}'
        code = self._code_reads('codes', 'periodo')
        wiz = self.env['ai.skill.capture.wizard'].with_user(
            self.user_a,
        ).create({
            'skill_code': skill.command,
            'skill_name': 'Kept',
            'description': 'hint',
            'procedure': 'proc',
            'code_body': code,
            'param_schema': authored,
            'arg_hint': 'codes=ABC',
            'existing_skill_id': skill.id,
            'from_chat': True,
        })
        wiz.action_create_draft()
        invalidate_recordset_fields(skill, None)
        self.assertEqual(json.loads(skill.param_schema), {
            'codes': {'type': 'string', 'desc': 'CSV'},
        })
        self.assertEqual(skill.arg_hint, 'codes=ABC')

    def test_wizard_merges_param_prose_without_invented_choices(self):
        skill = self._create_owned(
            self.env(user=self.user_a), 'prose',
            owner_id=self.user_a.id,
            param_schema='{"periodo":{"type":"string","desc":"YYYY-YYYY."}}',
        )
        wiz = self.env['ai.skill.capture.wizard'].with_user(
            self.user_a,
        ).create({
            'skill_code': skill.command,
            'skill_name': 'Prose',
            'description': 'help',
            'procedure': 'proc',
            'code_body': skill.code_body,
            'param_schema': skill.param_schema,
            'param_prose': 'codes is a CSV of short codes',
            'args_policy': 'ask',
            'existing_skill_id': skill.id,
            'from_chat': True,
        })
        rewritten = self._code_reads('periodo', 'codes')
        wiz.with_context(
            param_author_extracted={
                'codes': {
                    'type': 'string',
                    'desc': 'CSV of codes.',
                    'choices_model': 'demo.item',
                    'choices_code': 'x_code',
                },
            },
            param_code_rewritten=rewritten,
        ).action_create_draft()
        invalidate_recordset_fields(skill, None)
        schema = json.loads(skill.param_schema)
        self.assertIn('periodo', schema)
        self.assertEqual(schema['codes']['desc'], 'CSV of codes.')
        self.assertNotIn('choices_model', schema['codes'])
        self.assertEqual(skill.args_policy, 'ask')
        self.assertIn('codes=…', skill.arg_hint)
        self.assertIn('codes = codes', skill.code_body)
        self.assertIn('periodo = periodo', skill.code_body)

    def test_wizard_keeps_named_choices_from_prose(self):
        skill = self._create_owned(
            self.env(user=self.user_a), 'live',
            owner_id=self.user_a.id,
        )
        wiz = self.env['ai.skill.capture.wizard'].with_user(
            self.user_a,
        ).create({
            'skill_code': skill.command,
            'skill_name': 'Live',
            'description': 'help',
            'procedure': 'proc',
            'code_body': skill.code_body,
            'param_prose': 'codes from demo.item x_code',
            'existing_skill_id': skill.id,
            'from_chat': True,
        })
        rewritten = self._code_reads('codes')
        wiz.with_context(
            param_author_extracted={
                'codes': {
                    'type': 'string',
                    'desc': 'CSV of codes.',
                    'choices_model': 'demo.item',
                    'choices_code': 'x_code',
                },
            },
            param_code_rewritten=rewritten,
        ).action_create_draft()
        invalidate_recordset_fields(skill, None)
        schema = json.loads(skill.param_schema)
        self.assertEqual(schema['codes']['choices_model'], 'demo.item')
        self.assertEqual(schema['codes']['choices_code'], 'x_code')
        self.assertIn('codes = codes', skill.code_body)

    def test_wizard_keeps_schema_when_prose_is_rejected(self):
        skill = self._create_owned(
            self.env(user=self.user_a), 'keep',
            owner_id=self.user_a.id,
            param_schema='{"periodo":{"type":"string","desc":"YYYY-YYYY."}}',
        )
        wiz = self.env['ai.skill.capture.wizard'].with_user(
            self.user_a,
        ).create({
            'skill_code': skill.command,
            'skill_name': 'Keep',
            'description': 'help',
            'procedure': 'proc',
            'code_body': self._code_reads('periodo'),
            'param_schema': skill.param_schema,
            'param_prose': 'asdf qwerty',
            'existing_skill_id': skill.id,
            'from_chat': True,
        })
        wiz.with_context(param_author_extracted={
            '_reject': True,
        }).action_create_draft()
        invalidate_recordset_fields(skill, None)
        self.assertEqual(json.loads(skill.param_schema), {
            'periodo': {'type': 'string', 'desc': 'YYYY-YYYY.'},
        })

    def _param_lines(self, *rows):
        cmds = []
        for i, row in enumerate(rows):
            cmds.append((0, 0, {
                'sequence': 10 * (i + 1),
                'label': row.get('label') or '',
                'desc': row.get('desc') or '',
                'default': row.get('default') or '',
                'key': row.get('key') or '',
            }))
        return cmds

    def test_wizard_create_empty_lines_sets_none(self):
        skill = self._create_owned(
            self.env(user=self.user_a), 'none',
            owner_id=self.user_a.id,
        )
        wiz = self.env['ai.skill.capture.wizard'].with_user(
            self.user_a,
        ).create({
            'skill_code': skill.command,
            'skill_name': 'None',
            'description': 'help',
            'procedure': 'proc',
            'code_body': 'result = {"formatted_text": "<p>ok</p>", "__return_direct__": True}',
            'existing_skill_id': skill.id,
            'from_chat': True,
        })
        wiz.action_create_draft()
        invalidate_recordset_fields(skill, None)
        self.assertFalse(skill.param_schema)
        self.assertEqual(skill.args_policy, 'none')

    def test_wizard_lines_to_schema_label_desc_default(self):
        skill = self._create_owned(
            self.env(user=self.user_a), 'rows',
            owner_id=self.user_a.id,
        )
        wiz = self.env['ai.skill.capture.wizard'].with_user(
            self.user_a,
        ).create({
            'skill_code': skill.command,
            'skill_name': 'Rows',
            'description': 'help',
            'procedure': 'proc',
            'code_body': self._code_reads('periodo'),
            'param_line_ids': self._param_lines({
                'label': 'Period',
                'desc': 'YYYY or YYYY-YYYY. Empty = 12 months.',
                'default': '',
                'key': 'periodo',
            }),
            'existing_skill_id': skill.id,
            'from_chat': True,
        })
        wiz.action_create_draft()
        invalidate_recordset_fields(skill, None)
        schema = json.loads(skill.param_schema)
        self.assertEqual(schema['periodo']['label'], 'Period')
        self.assertEqual(
            schema['periodo']['desc'],
            'YYYY or YYYY-YYYY. Empty = 12 months.',
        )
        self.assertNotIn('default', schema['periodo'])

    def test_skill_form_lines_sync_schema(self):
        skill = self._create_owned(
            self.env(user=self.user_a), 'form',
            owner_id=self.user_a.id,
            param_schema='{"periodo":{"type":"string","desc":"YYYY-YYYY."}}',
        )
        invalidate_recordset_fields(skill, None)
        self.assertEqual(len(skill.param_line_ids), 1)
        self.assertEqual(skill.param_line_ids[0].key, 'periodo')
        self.assertEqual(skill.param_line_ids[0].label, 'periodo')
        skill.write({
            'param_line_ids': [(1, skill.param_line_ids.id, {
                'label': 'Period',
                'desc': 'YYYY or YYYY-YYYY',
            })],
        })
        invalidate_recordset_fields(skill, None)
        schema = json.loads(skill.param_schema)
        self.assertEqual(schema['periodo']['label'], 'Period')
        self.assertEqual(schema['periodo']['desc'], 'YYYY or YYYY-YYYY')

    def test_fill_missing_param_lines_from_schema(self):
        skill = self.env['ai.skill'].with_context(
            skip_param_line_schema=True,
        ).with_user(self.user_a).create({
            'code': ('fillmiss_%s' % self._uid).replace('-', '_'),
            'command': 'fillmiss-%s' % self._uid,
            'name': 'Fill missing',
            'description': 'Fill missing',
            'content': 'procedure',
            'code_body': 'result = {"formatted_text": "<p>ok</p>", "__return_direct__": True}',
            'owner_id': self.user_a.id,
            'param_schema': '{"desde_hasta":{"type":"string","label":"Period","desc":"YYYY"}}',
        })
        self.assertFalse(skill.param_line_ids)
        filled = self.env['ai.skill']._fill_missing_param_lines()
        invalidate_recordset_fields(skill, None)
        self.assertIn(skill, filled)
        self.assertEqual(skill.param_line_ids.key, 'desde_hasta')
        self.assertEqual(skill.param_line_ids.label, 'Period')

    def test_factory_import_skip_does_not_rebuild_lines(self):
        skill = self._create_owned(
            self.env(user=self.user_a), 'skip',
            owner_id=self.user_a.id,
            param_schema='{"periodo":{"type":"string","desc":"YYYY"}}',
        )
        line_ids = skill.param_line_ids.ids
        skill.with_context(skip_param_line_schema=True).write({
            'param_schema': '{"mes":{"type":"string","desc":"YYYY-MM"}}',
        })
        invalidate_recordset_fields(skill, None)
        self.assertEqual(skill.param_line_ids.ids, line_ids)
        self.assertEqual(skill.param_line_ids.key, 'periodo')
        filled = self.env['ai.skill']._fill_missing_param_lines()
        self.assertFalse(skill in filled)

    def test_skill_form_adding_lines_lifts_none(self):
        skill = self._create_owned(
            self.env(user=self.user_a), 'lift',
            owner_id=self.user_a.id,
            args_policy='none',
            code_body=self._code_reads('year'),
        )
        skill.write({
            'param_line_ids': [(0, 0, {
                'label': 'Year',
                'desc': 'Calendar year',
                'key': 'year',
            })],
        })
        invalidate_recordset_fields(skill, None)
        self.assertEqual(skill.args_policy, 'default')
        self.assertIn('year', json.loads(skill.param_schema or '{}'))

    def test_wizard_lines_lift_none_policy(self):
        skill = self._create_owned(
            self.env(user=self.user_a), 'wizlift',
            owner_id=self.user_a.id,
            args_policy='none',
        )
        wiz = self.env['ai.skill.capture.wizard'].with_user(
            self.user_a,
        ).create({
            'skill_code': skill.command,
            'skill_name': 'Lift',
            'description': 'help',
            'procedure': 'proc',
            'code_body': self._code_reads('year'),
            'args_policy': 'none',
            'param_line_ids': self._param_lines({
                'label': 'Year',
                'desc': 'Calendar year',
                'key': 'year',
            }),
            'existing_skill_id': skill.id,
            'from_chat': True,
        })
        wiz.action_create_draft()
        invalidate_recordset_fields(skill, None)
        self.assertEqual(skill.args_policy, 'default')

    def test_skill_form_empty_lines_sets_none(self):
        skill = self._create_owned(
            self.env(user=self.user_a), 'clear',
            owner_id=self.user_a.id,
            param_schema='{"periodo":{"type":"string","desc":"YYYY"}}',
        )
        skill.write({'param_line_ids': [(5, 0, 0)]})
        invalidate_recordset_fields(skill, None)
        self.assertFalse(skill.param_schema)
        self.assertEqual(skill.args_policy, 'none')

    def test_wizard_injects_unread_schema_keys(self):
        skill = self._create_owned(
            self.env(user=self.user_a), 'unread',
            owner_id=self.user_a.id,
        )
        wiz = self.env['ai.skill.capture.wizard'].with_user(
            self.user_a,
        ).create({
            'skill_code': skill.command,
            'skill_name': 'Unread',
            'description': 'help',
            'procedure': 'proc',
            'code_body': 'result = {"formatted_text": "<p>ok</p>", "__return_direct__": True}',
            'param_line_ids': self._param_lines({
                'key': 'codes', 'desc': 'CSV of codes.', 'default': 'ABC',
            }),
            'existing_skill_id': skill.id,
            'from_chat': True,
        })
        wiz.action_create_draft()
        invalidate_recordset_fields(skill, None)
        self.assertIn('codes = codes', skill.code_body)
        self.assertIn('except NameError', skill.code_body)

    def test_wizard_adapts_code_from_schema_without_prose(self):
        skill = self._create_owned(
            self.env(user=self.user_a), 'adapt',
            owner_id=self.user_a.id,
            param_schema='{"locations":{"type":"string","desc":"CSV"}}',
        )
        rewritten = self._code_reads('locations')
        wiz = self.env['ai.skill.capture.wizard'].with_user(
            self.user_a,
        ).create({
            'skill_code': skill.command,
            'skill_name': 'Adapt',
            'description': 'help',
            'procedure': 'proc',
            'code_body': 'result = {"formatted_text": "<p>ok</p>", "__return_direct__": True}',
            'param_schema': skill.param_schema,
            'existing_skill_id': skill.id,
            'from_chat': True,
        })
        wiz.with_context(param_code_rewritten=rewritten).action_create_draft()
        invalidate_recordset_fields(skill, None)
        self.assertIn('locations = locations', skill.code_body)
        self.assertEqual(json.loads(skill.param_schema), {
            'locations': {'type': 'string', 'desc': 'CSV'},
        })

    def test_list_for_agent_orders_mine_extra_injected_native(self):
        mine_b = self._create_owned(
            self.env(user=self.user_a), 'zz-b',
            owner_id=self.user_a.id,
        )
        mine_a = self._create_owned(
            self.env(user=self.user_a), 'zz-a',
            owner_id=self.user_a.id,
        )
        extra = self._create_owned(self.env, 'mm-extra')
        injected = self._create_owned(
            self.env, 'zz-inj', source_module='pns_ai_mcp',
        )
        native = self._create_owned(
            self.env, 'aa-sys', is_system=True,
        )
        rows = self.env['ai.skill'].with_user(self.user_a).list_for_agent(
            'pns_ai_mcp',
        )
        codes = {
            mine_a.command, mine_b.command, extra.command,
            injected.command, native.command,
        }
        ours = [r['code'] for r in rows if r['code'] in codes]
        self.assertEqual(ours, [
            mine_a.command, mine_b.command, extra.command,
            injected.command, native.command,
        ])
        by_code = {r['code']: r for r in rows if r['code'] in codes}
        self.assertTrue(by_code[mine_a.command]['mine'])
        self.assertFalse(by_code[extra.command]['factory'])
        self.assertTrue(by_code[injected.command]['factory'])
        self.assertFalse(by_code[injected.command]['is_system'])
        self.assertTrue(by_code[native.command]['is_system'])
