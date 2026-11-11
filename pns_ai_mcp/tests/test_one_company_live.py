# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""With two companies, AI reads and writes where it is told, and nowhere else.

The user belongs to A and B, A is the default. Without a screen (MCP,
Secretary) the read box and an approved Safe Plan see A only, whatever the
context says. With a screen (Chatboo on the web) they see what it ticks,
among the user's own companies.
"""
import uuid
from unittest.mock import patch

from odoo import SUPERUSER_ID, api
from odoo.tests import tagged, TransactionCase
from odoo.tools import mute_logger

from odoo.addons.pns_ai_mcp.controllers.controller_helpers import open_readonly_env
from odoo.addons.pns_ai_mcp.tests._helpers import (
    SKIP_CONTACT_ORIGIN,
    _test_cursor_view,
    create_test_user,
)
from odoo.addons.pns_ai_mcp.utils.one_company import SCREEN_COMPANIES
from odoo.addons.pns_ai_mcp.utils.skill_runtime import bootstrap_skill_code_body


def _flush(env):
    flush_all = getattr(env, 'flush_all', None)
    if flush_all is not None:
        flush_all()
    else:
        env['base'].flush()


def _forget(env):
    if hasattr(env, 'invalidate_all'):
        env.invalidate_all()
    else:
        env['res.partner'].invalidate_cache()


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestOneCompanyLive(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, **SKIP_CONTACT_ORIGIN))
        tag = uuid.uuid4().hex[:8]
        Company = self.env['res.company'].sudo()
        self.company_a = Company.create({'name': 'ACME A %s' % tag})
        self.company_b = Company.create({'name': 'ACME B %s' % tag})
        Partner = self.env['res.partner'].sudo()
        self.partner_a = Partner.create({
            'name': 'Cliente A %s' % tag, 'company_id': self.company_a.id, 'ref': 'a0',
        })
        self.partner_b = Partner.create({
            'name': 'Cliente B %s' % tag, 'company_id': self.company_b.id, 'ref': 'b0',
        })
        both = [self.company_a.id, self.company_b.id]
        self.user = create_test_user(
            self.env, prefix='pns_one_company',
            groups=[self.env.ref(x).id for x in (
                'base.group_user',
                'base.group_partner_manager',
                'pns_ai_mcp.group_ai_writer',
            )],
            company_ids=[(6, 0, both)],
            company_id=self.company_a.id,
        )
        self.switcher = dict(SKIP_CONTACT_ORIGIN, allowed_company_ids=both)
        _flush(self.env)

    def _shared_cursor(self):
        """Box A and the plan run inside this test's transaction.

        The read box marks its fresh cursor READ ONLY; mid-transaction
        PostgreSQL refuses that, so here it is skipped.
        """
        view = _test_cursor_view(self.env.cr)
        real_execute = view.execute

        def execute(query, *args, **kwargs):
            if str(query).strip().upper() == 'SET TRANSACTION READ ONLY':
                return None
            return real_execute(query, *args, **kwargs)

        view.execute = execute
        return view, patch.object(
            type(self.env.registry), 'cursor', lambda self, *a, **kw: view,
        )

    def _ids(self):
        return [self.partner_a.id, self.partner_b.id]

    def test_without_the_ai_the_switcher_shows_both(self):
        env = api.Environment(self.env.cr, self.user.id, self.switcher)
        seen = env['res.partner'].search([('id', 'in', self._ids())])
        self.assertEqual(set(seen.ids), set(self._ids()))

    def test_read_box_works_in_the_default_company(self):
        base_env = api.Environment(self.env.cr, self.user.id, self.switcher)
        _view, shared = self._shared_cursor()
        with shared:
            ro_env, ro_cr = open_readonly_env(base_env)
            try:
                self.assertEqual(ro_env.company, self.company_a)
                self.assertEqual(ro_env.companies, self.company_a)
                seen = ro_env['res.partner'].search([('id', 'in', self._ids())])
                self.assertEqual(seen.ids, [self.partner_a.id])
            finally:
                ro_cr.rollback()
                ro_cr.close()

    def test_ai_code_does_not_see_the_other_company(self):
        base_env = api.Environment(self.env.cr, self.user.id, self.switcher)
        code = (
            "result = {'ids': env['res.partner'].search("
            "[('id', 'in', %r)]).ids}" % self._ids()
        )
        diag = {}
        _view, shared = self._shared_cursor()
        with shared:
            result = bootstrap_skill_code_body(
                base_env, code, skill_code='one_company_test', diag=diag,
            )
        self.assertTrue(result, diag)
        self.assertEqual(result['ids'], [self.partner_a.id])

    def _screen_ids(self, base_env):
        _view, shared = self._shared_cursor()
        with shared:
            ro_env, ro_cr = open_readonly_env(base_env)
            try:
                return (
                    ro_env['res.partner'].search([('id', 'in', self._ids())]).ids,
                    ro_env.company,
                )
            finally:
                ro_cr.rollback()
                ro_cr.close()

    def test_the_screen_company_is_the_one_the_ai_reads(self):
        ctx = dict(self.switcher, **{SCREEN_COMPANIES: [self.company_b.id]})
        seen, active = self._screen_ids(
            api.Environment(self.env.cr, self.user.id, ctx))
        self.assertEqual(seen, [self.partner_b.id])
        self.assertEqual(active, self.company_b)

    def test_the_screen_ticks_both_and_the_active_one_leads(self):
        ctx = dict(self.switcher, **{
            SCREEN_COMPANIES: [self.company_b.id, self.company_a.id]})
        seen, active = self._screen_ids(
            api.Environment(self.env.cr, self.user.id, ctx))
        self.assertEqual(set(seen), set(self._ids()))
        self.assertEqual(active, self.company_b)

    def test_a_screen_company_that_is_not_mine_is_ignored(self):
        other = self.env['res.company'].sudo().create({
            'name': 'ACME C %s' % uuid.uuid4().hex[:8]})
        ctx = dict(SKIP_CONTACT_ORIGIN, **{SCREEN_COMPANIES: [other.id]})
        seen, active = self._screen_ids(
            api.Environment(self.env.cr, self.user.id, ctx))
        self.assertEqual(seen, [self.partner_a.id])
        self.assertEqual(active, self.company_a)

    def _run_plan(self, partner, ref, screen=None):
        operation_data = {
            'plan_steps': [{
                'op': 'write', 'model': 'res.partner',
                'ids': [partner.id], 'values': {'ref': ref},
            }],
            'title': 'one company',
            'plan': ['write 1 res.partner'],
            'danger_level': 'low',
        }
        if screen:
            operation_data[SCREEN_COMPANIES] = screen
        view, shared = self._shared_cursor()
        with shared:
            root = api.Environment(view, SUPERUSER_ID, self.switcher)
            op = root['ai.safe.operation'].create_verification(
                operation_type='write',
                model_name='res.partner',
                records_count=1,
                changes_info={'plan': ['write 1 res.partner'], 'danger_level': 'low'},
                user_id=self.user.id,
                tool_name='test_one_company_live',
                operation_data=operation_data,
            )
            op.with_user(self.user.id)._confirm_by_user()
            try:
                return root(user=self.user.id)['ai.safe.operation'].browse(
                    op.id).execute_plan_now()
            finally:
                _forget(self.env)

    def test_plan_writes_in_the_default_company(self):
        self.assertTrue(self._run_plan(self.partner_a, 'a1'))
        self.assertEqual(self.partner_a.ref, 'a1')

    @mute_logger('odoo.addons.pns_ai_mcp.models.safe_operation')
    def test_plan_cannot_touch_the_other_company(self):
        try:
            self._run_plan(self.partner_b, 'b1')
        except Exception:
            pass
        self.assertEqual(self.partner_b.ref, 'b0')

    def test_a_plan_asked_in_the_other_company_runs_there(self):
        self.assertTrue(self._run_plan(
            self.partner_b, 'b2', screen=[self.company_b.id]))
        self.assertEqual(self.partner_b.ref, 'b2')
