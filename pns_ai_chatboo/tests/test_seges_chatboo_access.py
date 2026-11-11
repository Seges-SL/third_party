# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: tests de la entrega E0′ (no regresión del parche 11, cubierto en parte por 3.1.879). Ver docs/pendiente/parches_pns_ai.md
"""Parche 11 (PNS-82), en lo que cubre el fabricante desde 3.1.879: los
métodos del flujo de chips dejan de ser públicos y un adjunto solo se engancha
a la sesión de su creador.

Portado de la rama 14.0-pns-ai-correcciones (entrega E2) y adaptado a 3.1.879
(docs/specs/comparacion_pns_ai_3-1-879.md, §4.1). ``test_fulfill_client_export_claims_own``
está en ``test_seges_chatboo_export.py`` (E1′, PNS-07).

E2′ (parche 11 adaptado a 3.1.879): ``test_unlink_own_session_keeps_foreign``,
``test_cron_unlink_sudo_keeps_foreign`` y, en ``test_claim_filters_in_python``, el
adjunto con ``res_model`` y ``res_id = 0``, que no se engancha (criterio del
fabricante, decisión 7 de docs/pendiente/e2_propuesta_3879.md).
"""

import base64
import json
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

from odoo.addons.pns_ai_mcp.controllers.context_builder import guarded_getattr
from odoo.addons.pns_ai_mcp.controllers.validators_base import (
    blocked_private_attr,
)
from odoo.addons.pns_ai_mcp.utils.session_download import persist_turn_file
from odoo.addons.pns_base.utils.portable_io import write_json_attachment

from .common import SegesChatbooCase

RENAMED = (
    ('claim_turn_file_chips', '_claim_turn_file_chips'),
    ('apply_assistant_download_chips', '_apply_assistant_download_chips'),
    ('stage_assistant_download_chips', '_stage_assistant_download_chips'),
    ('consume_staged_assistant_download_chips', '_consume_staged_assistant_download_chips'),
)
BODY_A = b'seges-e2-a-body'
XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


class _SegesChatbooData(SegesChatbooCase):  # pylint: disable=too-many-instance-attributes
    """Usuarios, sesiones y adjuntos comunes."""

    def setUp(self):
        super().setUp()
        self.user_a = new_test_user(
            self.env, login='seges_e2_a', groups='base.group_user',
            password='seges_e2_a',
        )
        self.user_b = new_test_user(
            self.env, login='seges_e2_b', groups='base.group_user',
            password='seges_e2_b',
        )
        self.user_p = new_test_user(
            self.env, login='seges_e2_portal', groups='base.group_portal',
            password='seges_e2_portal',
        )
        self.user_admin = new_test_user(
            self.env, login='seges_e2_admin',
            groups='base.group_user,base.group_system,pns_ai_mcp.group_ai_admin',
        )
        Session = self.env['chatboo.session']
        self.cs_a = Session.with_user(self.user_a).create({'name': 'Seges E2 A'})
        self.cs_b = Session.with_user(self.user_b).create({'name': 'Seges E2 B'})
        Attachment = self.env['ir.attachment']
        self.att_a = Attachment.with_user(self.user_a).create({
            'name': 'seges-e2-a.xlsx',
            'datas': base64.b64encode(BODY_A),
            'mimetype': 'application/octet-stream',
        })
        self.att_a_rm0 = Attachment.with_user(self.user_a).create({
            'name': 'seges-e2-a-rm0.bin',
            'datas': base64.b64encode(BODY_A),
            'mimetype': 'application/octet-stream',
            'res_model': 'res.partner',
            'res_id': 0,
        })
        self.att_b = Attachment.with_user(self.user_b).create({
            'name': 'seges-e2-b.bin',
            'datas': base64.b64encode(b'seges-e2-b-body'),
            'mimetype': 'application/octet-stream',
        })
        self.att_cfg = write_json_attachment(
            self.env(user=self.user_admin), 'seges-e2-config.json', {'k': 'secret'},
        )

    def _atts(self):
        self.env['base'].flush()
        ids = (self.att_a + self.att_a_rm0 + self.att_b + self.att_cfg).ids
        self.env.cr.execute(
            'SELECT id, res_model, res_id, create_uid FROM ir_attachment '
            'WHERE id IN %s ORDER BY id', (tuple(ids),))
        return self.env.cr.fetchall()

    def _staged(self):
        self.env['base'].flush()
        self.env.cr.execute(
            'SELECT id, staged_assistant_files FROM chatboo_session '
            'WHERE id IN %s ORDER BY id', ((self.cs_a.id, self.cs_b.id),))
        return self.env.cr.fetchall()

    def _att_row(self, att_id):
        self.env['base'].flush()
        self.env.cr.execute(
            'SELECT res_model, res_id, create_uid FROM ir_attachment WHERE id = %s',
            (att_id,))
        return self.env.cr.fetchone()

    def _all_chips(self):
        """Los tres formatos de chip para cada adjunto ajeno."""
        chips = []
        for att in (self.att_a, self.att_a_rm0, self.att_cfg):
            chips.append({'attachment_id': att.id})
            chips.append({'url': f'/pns_ai_mcp/session_file/{att.id}/x.xlsx'})
            chips.append({'url': f'/web/content/{att.id}'})
        return chips

    def _sudo_job(self, user, session, **vals):
        """3.1.879: el job no se crea por RPC (ACL 1,0,0,0); el chat lo crea en sudo."""
        return self.env['chatboo.async.request'].sudo().create(dict(
            {'session_id': session.id, 'user_id': user.id, 'prompt': 'seges e2'},
            **vals))


@tagged('post_install', '-at_install', 'pns_ai_chatboo', 'seges_e0')
class TestSegesChatbooRpc(_SegesChatbooData):

    def test_control_session_ok(self):
        for login in ('seges_e2_b', 'seges_e2_portal'):
            res = self._rpc(login, 'res.users', 'context_get', [])
            self.assertIn('result', res, res)

    def test_claim_refused_rpc(self):
        before = self._atts()
        chips = self._all_chips()
        for login in ('seges_e2_b', 'seges_e2_portal'):
            for session in (self.cs_b, self.cs_a):
                for old, new in (RENAMED[0],):
                    res = self._rpc(
                        login, 'chatboo.session', old, [[session.id], chips])
                    self._assert_refused(res, private=False)
                    res = self._rpc(
                        login, 'chatboo.session', new, [[session.id], chips])
                    self._assert_refused(res, private=True)
        self.assertEqual(self._atts(), before)

    def test_flow_methods_refused_rpc(self):
        before = self._atts()
        staged = self._staged()
        chips = self._all_chips()
        for login in ('seges_e2_b', 'seges_e2_portal'):
            for old, new in RENAMED[1:]:
                for name, private in ((old, False), (new, True)):
                    args = [[self.cs_b.id]]
                    if not name.endswith('consume_staged_assistant_download_chips'):
                        args.append(chips)
                    res = self._rpc(login, 'chatboo.session', name, args)
                    self._assert_refused(res, private=private)
        self.assertEqual(self._staged(), staged)
        self.assertEqual(self._atts(), before)

    def test_foreign_download_denied(self):
        for att in (self.att_a, self.att_cfg):
            resp = self._get(
                'seges_e2_b', f'/pns_ai_mcp/session_file/{att.id}')
            self.assertEqual(resp.status_code, 404)
            resp = self._get('seges_e2_b', f'/web/content/{att.id}')
            self.assertNotEqual(resp.status_code, 200)
            self.assertNotIn(BODY_A, resp.content)
        resp = self._get(
            'seges_e2_a', f'/pns_ai_mcp/session_file/{self.att_a.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, BODY_A)

    def test_staged_buffer_does_not_hijack(self):
        """H-2: búfer + request_cancel por RPC real."""
        before = self._atts()
        res = self._rpc('seges_e2_b', 'chatboo.session', 'write', [
            [self.cs_b.id],
            {'staged_assistant_files': json.dumps([
                {'attachment_id': self.att_a.id},
                {'url': f'/pns_ai_mcp/session_file/{self.att_cfg.id}'},
            ])},
        ])
        self.assertIs(res.get('result'), True, res)
        job = self._sudo_job(self.user_b, self.cs_b)
        res = self._rpc(
            'seges_e2_b', 'chatboo.async.request', 'request_cancel', [[job.id]])
        self.assertIs(res.get('result'), True, res)
        self.assertEqual(self._atts(), before)
        for att in (self.att_a, self.att_cfg):
            row = self._att_row(att.id)
            self.assertFalse(row[0])
            self.assertFalse(row[1])
            resp = self._get(
                'seges_e2_b', f'/pns_ai_mcp/session_file/{att.id}')
            self.assertEqual(resp.status_code, 404)

    def test_unlink_own_session_keeps_foreign(self):
        """Parche 11 adaptado (E2′). Falla sin el parche (borraría el adjunto de A)."""
        # Enganche anterior a la corrección, simulado en sudo.
        self.att_a.sudo().write({
            'res_model': 'chatboo.session', 'res_id': self.cs_b.id})
        own = self.env['ir.attachment'].with_user(self.user_b).create({
            'name': 'seges-e2-own.png',
            'datas': base64.b64encode(b'seges-e2-own'),
            'mimetype': 'image/png',
            'res_model': 'chatboo.session',
            'res_id': self.cs_b.id,
        })
        own_id = own.id
        res = self._rpc(
            'seges_e2_b', 'chatboo.session', 'unlink', [[self.cs_b.id]])
        self.assertIn('result', res, res)
        self.assertIsNone(self._att_row(own_id))
        row = self._att_row(self.att_a.id)
        self.assertIsNotNone(row)
        self.assertFalse(row[0])
        self.assertFalse(row[1])
        self.assertEqual(row[2], self.user_a.id)
        resp = self._get(
            'seges_e2_a', f'/pns_ai_mcp/session_file/{self.att_a.id}')
        self.assertEqual(resp.status_code, 200)
        resp = self._get(
            'seges_e2_b', f'/pns_ai_mcp/session_file/{self.att_a.id}')
        self.assertEqual(resp.status_code, 404)

    def test_unlink_foreign_session_refused(self):
        img = self.env['ir.attachment'].with_user(self.user_a).create({
            'name': 'seges-e2-img.png',
            'datas': base64.b64encode(b'seges-e2-img'),
            'mimetype': 'image/png',
            'res_model': 'chatboo.session',
            'res_id': self.cs_a.id,
        })
        res = self._rpc(
            'seges_e2_b', 'chatboo.session', 'unlink', [[self.cs_a.id]])
        self._assert_refused(res, private=True)
        self.env.cr.execute(
            'SELECT count(*) FROM chatboo_session WHERE id = %s', (self.cs_a.id,))
        self.assertEqual(self.env.cr.fetchone()[0], 1)
        self.assertIsNotNone(self._att_row(img.id))


@tagged('post_install', '-at_install', 'pns_ai_chatboo', 'seges_e0')
class TestSegesChatbooFlows(_SegesChatbooData):

    def _hung(self, att_id):
        return self._att_row(att_id)[:2]

    def test_own_download_claimed_and_served(self):
        env_a = self.env(user=self.user_a)
        chip = persist_turn_file(
            env_a, self.cs_a.id, b'seges-e2-own', 'seges-e2.xlsx', mimetype=XLSX)
        self.assertTrue(chip)
        att_id = chip['attachment_id']
        self.cs_a.with_user(self.user_a)._claim_turn_file_chips([chip])
        row = self._att_row(att_id)
        self.assertEqual(row, ('chatboo.session', self.cs_a.id, self.user_a.id))
        resp = self._get('seges_e2_a', chip['url'])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b'seges-e2-own')
        resp = self._get('seges_e2_a', f'/web/content/{att_id}')
        self.assertEqual(resp.status_code, 200)
        for url in (chip['url'], f'/web/content/{att_id}'):
            resp = self._get('seges_e2_b', url)
            self.assertNotEqual(resp.status_code, 200)

    def test_claim_filters_in_python(self):
        cs_b_b = self.cs_b.with_user(self.user_b)
        # (a) y (b): el adjunto es de A y la sesión de B; sudo no levanta el filtro.
        cs_b_b._claim_turn_file_chips([{'attachment_id': self.att_a.id}])
        cs_b_b.sudo()._claim_turn_file_chips([{'attachment_id': self.att_a.id}])
        # (c) B contra la sesión de A, con un huérfano propio.
        cs_a_as_b = self.env['chatboo.session'].with_user(self.user_b).browse(
            self.cs_a.id)
        cs_a_as_b._claim_turn_file_chips([{'attachment_id': self.att_b.id}])
        self.assertEqual(self._hung(self.att_a.id), (None, None))
        self.assertEqual(self._hung(self.att_b.id), (None, None))
        # (d) control: A engancha el suyo. El suyo con res_model y res_id=0 no
        # se engancha: criterio del fabricante (decisión 7 de E2′).
        self.cs_a.with_user(self.user_a)._claim_turn_file_chips([
            {'attachment_id': self.att_a.id},
            {'attachment_id': self.att_a_rm0.id},
        ])
        self.assertEqual(
            self._hung(self.att_a.id), ('chatboo.session', self.cs_a.id))
        self.assertEqual(self._hung(self.att_a_rm0.id), ('res.partner', 0))

    def test_save_to_session_claims_only_own(self):
        env_a = self.env(user=self.user_a)
        csv_b64 = base64.b64encode(b'a;b').decode()
        # Crear el job no arranca el hilo del worker ni llama a ningún proveedor.
        job = self._sudo_job(self.user_a, self.cs_a, files=json.dumps([{
            'name': 'seges-e2.csv', 'mimetype': 'text/csv',
            'data': 'data:text/csv;base64,' + csv_b64,
        }])).with_user(self.user_a)
        chip_own = persist_turn_file(
            env_a, self.cs_a.id, b'seges-e2-own', 'seges-e2-own.xlsx',
            mimetype=XLSX)
        job._save_to_session('ok', {'assistant_files': [
            chip_own,
            {'attachment_id': self.att_cfg.id,
             'url': f'/pns_ai_mcp/session_file/{self.att_cfg.id}'},
        ]}, error=None)
        self.env['base'].flush()
        self.env.cr.execute(
            "SELECT id FROM ir_attachment WHERE res_model = 'chatboo.session' "
            "AND res_id = %s AND name = 'seges-e2.csv'", (self.cs_a.id,))
        self.assertEqual(len(self.env.cr.fetchall()), 1)
        self.assertEqual(
            self._hung(chip_own['attachment_id']),
            ('chatboo.session', self.cs_a.id))
        self.assertEqual(self._hung(self.att_cfg.id), (None, None))
        messages = self.cs_a.with_user(self.user_a).get_messages()
        last = messages[-1]
        self.assertEqual(last.get('role'), 'assistant')
        self.assertIn(
            chip_own['attachment_id'],
            [f.get('attachment_id') for f in last.get('files') or []])

    def test_cron_unlink_sudo_keeps_foreign(self):
        """Parche 11 adaptado (E2′): varias sesiones en sudo, como `_cleanup_old_sessions`."""
        Attachment = self.env['ir.attachment']
        vals = {'mimetype': 'image/png'}
        own_a = Attachment.with_user(self.user_a).create(dict(
            vals, name='seges-e2-cron-a.png', datas=base64.b64encode(b'cron-a'),
            res_model='chatboo.session', res_id=self.cs_a.id))
        own_b = Attachment.with_user(self.user_b).create(dict(
            vals, name='seges-e2-cron-b.png', datas=base64.b64encode(b'cron-b'),
            res_model='chatboo.session', res_id=self.cs_b.id))
        # Adjunto de otro creador (admin) enganchado a la sesión de B, en sudo.
        self.att_cfg.sudo().write({
            'res_model': 'chatboo.session', 'res_id': self.cs_b.id})
        own_ids = (own_a.id, own_b.id)
        (self.cs_a + self.cs_b).sudo().unlink()
        for att_id in own_ids:
            self.assertIsNone(self._att_row(att_id))
        row = self._att_row(self.att_cfg.id)
        self.assertIsNotNone(row)
        self.assertFalse(row[0])
        self.assertFalse(row[1])
        self.assertEqual(row[2], self.user_admin.id)

    def test_public_names_gone(self):
        model = type(self.env['chatboo.session'])
        for old, new in RENAMED:
            self.assertFalse(hasattr(model, old), old)
            self.assertTrue(hasattr(model, new), new)

    def test_no_caller_uses_public_names(self):
        pattern = re.compile(
            r"(\.|def )(claim_turn_file_chips|apply_assistant_download_chips"
            r"|stage_assistant_download_chips"
            r"|consume_staged_assistant_download_chips)\b")
        found = []
        for module in ('pns_ai_chatboo', 'pns_ai_mcp'):
            path = get_module_path(module)
            for root, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if d not in ('tests', 'node_modules')]
                for fname in files:
                    if not fname.endswith(('.py', '.js', '.xml')):
                        continue
                    fpath = os.path.join(root, fname)
                    with open(fpath, encoding='utf-8', errors='replace') as handle:
                        for num, line in enumerate(handle, 1):
                            if pattern.search(line):
                                found.append(f'{fpath}:{num}')
        self.assertEqual(found, [])


@tagged('post_install', '-at_install', 'pns_ai_chatboo', 'seges_e0')
class TestSegesChatbooSandbox(TransactionCase):

    def test_names_in_denylist(self):
        # 3.1.879 bloquea todo nombre con `_` en el sandbox, no una lista.
        for _old, new in RENAMED:
            self.assertTrue(blocked_private_attr(new), new)
            with self.assertRaises(AttributeError):
                guarded_getattr(object(), new)
