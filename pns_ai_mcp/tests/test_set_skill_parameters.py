# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
""" Owned extras resolve by stem, prefix, or name; factory stays blocked. """
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


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestSetSkillParameters(TransactionCase):

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
        self.user_a = create_test_user(self.env, prefix='pns_set_params_a', groups=writers)
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
            'content': 'procedure',
            'code_body': (
                'try:\n'
                '    codes = codes\n'
                'except NameError:\n'
                '    codes = None\n'
                'result = {"formatted_text": "<p>ok</p>", "__return_direct__": True}'
            ),
        }
        vals.update(extra)
        return env['ai.skill'].create(vals)

    def test_resolve_stem_and_prefixed_command(self):
        skill = self._create_owned(
            self.env(user=self.user_a), 'alpha',
            owner_id=self.user_a.id,
        )
        Skill = self.env['ai.skill'].with_user(self.user_a)
        hits, kind = Skill.resolve_owned_for_params(skill.command)
        self.assertEqual(kind, 'one')
        self.assertEqual(hits, skill)
        hits, kind = Skill.resolve_owned_for_params(skill.code)
        self.assertEqual(kind, 'one')
        self.assertEqual(hits, skill)

    def test_resolve_by_name_word(self):
        skill = self._create_owned(
            self.env(user=self.user_a), 'beta',
            owner_id=self.user_a.id,
            name='Unique Widget %s' % self._uid,
        )
        Skill = self.env['ai.skill'].with_user(self.user_a)
        hits, kind = Skill.resolve_owned_for_params('Widget %s' % self._uid)
        self.assertEqual(kind, 'one')
        self.assertEqual(hits, skill)

    def test_ambiguous_name_returns_picks(self):
        marker = 'SharedMark %s' % self._uid
        one = self._create_owned(
            self.env(user=self.user_a), 'one',
            owner_id=self.user_a.id,
            name='%s One' % marker,
        )
        two = self._create_owned(
            self.env(user=self.user_a), 'two',
            owner_id=self.user_a.id,
            name='%s Two' % marker,
        )
        Skill = self.env['ai.skill'].with_user(self.user_a)
        hits, kind = Skill.resolve_owned_for_params(marker)
        self.assertEqual(kind, 'picks')
        self.assertEqual(hits, one | two)
        picks = Skill.owned_skill_picks(hits)
        codes = {row['code'] for row in picks}
        self.assertIn(one.command, codes)
        self.assertIn(two.command, codes)

    def test_factory_and_system_blocked(self):
        factory = self._create_owned(
            self.env, 'factory', source_module='pns_ai_mcp',
        )
        system = self._create_owned(self.env, 'sys', is_system=True)
        Skill = self.env['ai.skill'].with_user(self.user_a)
        with self.assertRaises(UserError) as err:
            Skill.resolve_owned_for_params(factory.command)
        self.assertIn('You can only change skills you created', str(err.exception))
        with self.assertRaises(UserError) as err:
            Skill.resolve_owned_for_params(system.command)
        self.assertIn('System skills', str(err.exception))

    def test_missing_token_raises(self):
        Skill = self.env['ai.skill'].with_user(self.user_a)
        with self.assertRaises(UserError) as err:
            Skill.resolve_owned_for_params('no-such-%s' % self._uid)
        self.assertIn('There is no skill named', str(err.exception))

    def test_empty_token_lists_owned(self):
        skill = self._create_owned(
            self.env(user=self.user_a), 'mine',
            owner_id=self.user_a.id,
        )
        Skill = self.env['ai.skill'].with_user(self.user_a)
        hits, kind = Skill.resolve_owned_for_params('')
        self.assertEqual(kind, 'picks')
        self.assertIn(skill, hits)
