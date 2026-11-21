# -*- coding: utf-8 -*-
"""Prueba de solo lectura del manual pns_ai 3.1.973 (docs/specs/manual_pns_ai_3973.md).

Comprueba en una BD de laboratorio lo que el manual da por hecho (bloques M1 a M12)
frente a lo previsto, sacado del código de la rama 14.0-pns-ai-informe (cada valor
lleva su cita en un comentario).

Uso, solo en el laboratorio, con el shell de Odoo leyendo este archivo por stdin:
    odoo-dev 14 shell < docs/pendiente/lab_3973/manual_lab.py

Cómo se protege contra escrituras (Odoo 14 del contenedor odoo-dev:14):
- No usa env.cr: abre un cursor nuevo con env.registry.cursor(); su primera orden es
  SET TRANSACTION READ ONLY y comprueba con SHOW transaction_read_only que vale «on»
  (si no, código 20). La transacción empieza con la primera orden: el cursor nuevo no
  lanza ninguna al crearse (odoo/sql_db.py:250-257 y :405-423).
- Repite el SHOW antes de cada bloque y no hace commit ni rollback a mitad: tras un
  commit o un rollback empezaría una transacción nueva de lectura y escritura
  (sql_db.py:449-468). El rollback y el close van solo en el finally.
- Ante el primer error de un bloque (de base de datos o interno) para: los bloques que
  quedan salen «NO EJECUTADO» y el código es 20. Se imprime el bloque y el tipo de la
  excepción (con su SQLSTATE si lo tiene), nunca su mensaje.
- Termina siempre con sys.exit: con SystemExit el cursor del shell no hace commit
  (odoo/cli/shell.py:112-119; sql_db.py:148-153) y el código llega a la terminal.

Salida: solo nombres técnicos, etiquetas, recuentos, versiones y valores de las claves
numéricas. Nunca datos de registros, claves ni valores de parámetros no numéricos.

Códigos: 0 todo IGUAL · 1 algún DISTINTO · 8 no concluyente (M1 distinto: BD no
actualizada; o M12 sin ningún modelo de los tres módulos) · 20 error interno o
escritura rechazada. Si coinciden varios, manda el mayor: 20 > 8 > 1 > 0 (un DISTINTO
en un bloque y un NO CONCLUYENTE en otro dan 8; los DISTINTO siguen saliendo en sus
bloques). Última línea: «CÓDIGO: <n>».

Compatible con Python 3.7 (el del contenedor: 3.7.3).
"""
import os
import re
import sys

MODS = ('pns_base', 'pns_ai_mcp', 'pns_ai_chatboo')

IGUAL = 'IGUAL'
DISTINTO = 'DISTINTO'
NO_CONCLUYENTE = 'NO CONCLUYENTE'
NO_EJECUTADO = 'NO EJECUTADO'
INFORMATIVO = 'INFORMATIVO'
ERROR = 'ERROR'

COD_OK = 0
COD_DISTINTO = 1
COD_NO_CONCLUYENTE = 8
COD_ERROR = 20

# Marca de las BD neutralizadas por el kit (claude-odoo-kit/entorno/entorno.sh:530-533
# la lee y :563 la escribe). Solo se mira si existe; su valor no se imprime.
MARCA_NEUTRALIZADA = 'odoo_dev.neutralizada'

# ---------------------------------------------------------------- lo previsto

# M1. pns_base/__manifest__.py:8; pns_ai_mcp/__manifest__.py:8;
# pns_ai_chatboo/__manifest__.py:7
M1_VERSIONES = {
    'pns_base': '14.0.1.2.69',
    'pns_ai_mcp': '14.0.3.1.973',
    'pns_ai_chatboo': '14.0.2.1.587',
}

# M2. pns_ai_mcp/security/security_groups.xml:10-50; nombres en pns_ai_mcp/i18n/es.po
# (:2858 categoría, :2864, :4860, :4866, :4872, :2871).
M2_CATEGORIA = ('pns_ai_mcp.module_category_ai', 'Inteligencia Artificial')
_W = 'pns_ai_mcp.group_ai_writer'
_U = 'pns_ai_mcp.group_ai_external_url'
_A = 'pns_ai_mcp.group_ai_external_api'
_C = 'pns_ai_mcp.group_ai_conversational'
_ADM = 'pns_ai_mcp.group_ai_admin'
M2_GRUPOS = (
    (_W, 'IA Escritor', ('base.group_user',)),
    (_U, 'IA URL externa', ('base.group_user',)),
    (_A, 'IA API externa', ('base.group_user',)),
    (_C, 'IA Conversacional', ('base.group_user',)),
    (_ADM, 'IA Administrador', (_W, _U, _A, _C)),
)

# M3. Salida de docs/pendiente/lab_3973/menus.py (sin el nombre en inglés): xmlid,
# nombre es, padre, grupos. Cada fila: archivo:línea del menuitem.
_SEC = 'pns_ai_mcp.menu_ai_security'
_MAIN = 'pns_ai_mcp.menu_mcp_main'
_CON = 'pns_ai_mcp.menu_ai_connections'
_KNOW = 'pns_ai_mcp.menu_ai_knowledge'
_WUA = (_W, _U, _A)
M3_MENUS = (
    ('pns_ai_mcp.menu_url_whitelist', 'Lista Blanca', _CON, (_ADM,)),          # url_whitelist_views.xml:79
    ('pns_ai_mcp.menu_ai_log', 'My Activity', _SEC, _WUA),                      # ai_log_views.xml:281
    ('pns_ai_mcp.menu_ai_log_admin', 'Activity', _SEC, (_ADM,)),                # ai_log_views.xml:288
    ('pns_ai_mcp.menu_ai_safe_operation', 'Mis Autorizaciones', _SEC, _WUA),    # safe_operation_views.xml:132
    ('pns_ai_mcp.menu_ai_safe_operation_admin', 'Autorizaciones', _SEC, (_ADM,)),  # safe_operation_views.xml:162
    ('pns_ai_mcp.menu_ai_domain_discovery', 'Descubrimiento', _KNOW, (_ADM,)),  # ai_domain_index_views.xml:66
    ('pns_ai_mcp.menu_ai_change_journal', 'Cambios aplicados', _SEC, (_ADM,)),  # ai_change_journal_views.xml:157
    ('pns_ai_mcp.menu_mcp_main', 'Motor de IA', '-', (_ADM, _W, _U, _A)),       # mcp_user_views.xml:145
    ('pns_ai_mcp.menu_ai_connections', 'Conexiones', _MAIN, (_ADM,)),           # mcp_user_views.xml:155
    ('pns_ai_mcp.menu_ai_knowledge', 'Conocimiento', _MAIN, (_ADM, _W)),        # mcp_user_views.xml:160
    ('pns_ai_mcp.menu_ai_security', 'Seguridad', _MAIN, (_ADM, _W, _U, _A)),    # mcp_user_views.xml:165
    ('pns_ai_mcp.menu_mcp_users', 'Usuarios', _SEC, (_ADM,)),                   # mcp_user_views.xml:172
    ('pns_ai_mcp.menu_mcp_settings', 'Ajustes', _MAIN, ('base.group_system',)),  # res_config_settings_views.xml:360
    ('pns_ai_mcp.menu_ai_provider', 'Proveedores', _CON, (_ADM,)),              # ai_menus.xml:6
    ('pns_ai_mcp.menu_ai_agent', 'Agentes', _MAIN, (_ADM,)),                    # ai_menus.xml:14
    ('pns_ai_mcp.menu_ai_skill', 'Habilidades', _KNOW, (_ADM,)),                # ai_menus.xml:21
    ('pns_ai_mcp.menu_ai_context', 'Contextos', _KNOW, (_ADM,)),                # ai_context_views.xml:202
    ('pns_ai_mcp.menu_ai_provider_role', 'Roles de proveedor', _CON, (_ADM,)),  # ai_provider_role_views.xml:74
    ('pns_ai_mcp.menu_external_server', 'Servidores externos', _CON, (_ADM,)),  # external_server_views.xml:324
    ('pns_ai_mcp.menu_ai_context_writer', 'Mis contextos', _KNOW, (_W,)),       # ai_operator_menus.xml:7
    ('pns_ai_mcp.menu_ai_skill_writer', 'Mis Habilidades', _KNOW, (_W,)),       # ai_operator_menus.xml:14
    ('pns_ai_chatboo.menu_chatboo_root', 'Chatboo', '-', ()),                   # chatboo_menus.xml:13
    ('pns_ai_chatboo.menu_chatboo_shared_pages', 'Páginas compartidas', _SEC, ()),  # chatboo_canvas_page_views.xml:75
)

# M4. (módulo, modelo con _, campo, etiqueta es, cita del msgid en <módulo>/i18n/es.po)
_CB = 'pns_ai_chatboo'
_MC = 'pns_ai_mcp'
_RCS = 'res_config_settings'
M4_ETIQUETAS = (
    # Ajustes de Chatboo (manual §20)
    (_CB, _RCS, 'chatboo_show_systray', 'Mostrar Chatboo en la barra del sistema', ':648'),
    (_CB, _RCS, 'chatboo_dataset_cache_max_mb', 'Copia oculta de la lista (MB)', ':808'),
    (_CB, _RCS, 'chatboo_query_data_ttl_hours', 'Horas que dura esa copia', ':814'),
    (_CB, _RCS, 'chatboo_history_retention_days', 'Retención de sesiones (días)', ':820'),
    (_CB, _RCS, 'chatboo_download_max_mb', 'Límite de descarga (MB)', ':833'),
    (_CB, _RCS, 'chatboo_upload_max_mb', 'Límite de subida (MB)', ':2113'),
    (_CB, _RCS, 'chatboo_allow_remote_voices', 'Permitir voces remotas', ':2418'),
    (_CB, _RCS, 'chatboo_chart_engine', 'Motor de gráficos', ':868'),
    (_CB, _RCS, 'chatboo_default_show_mode', 'Showmode por defecto', ':873'),
    (_CB, _RCS, 'chatboo_xlsx_float_decimals', 'Decimales', ':878'),
    (_CB, _RCS, 'chatboo_xlsx_thousands', 'Separador de millares en Excel', ':888'),
    # Ficha del agente Chatboo (manual §4 y §9)
    (_CB, 'ai_agent', 'chatboo_download_max_mb', 'Límite de descarga (MB)', ':833'),
    (_CB, 'ai_agent', 'chatboo_allow_remote_voices', 'Permitir voces remotas', ':2418'),
    # Ajustes del motor (manual §14 a §18)
    (_MC, _RCS, 'display_currency', 'Moneda de visualización', ':3870'),
    (_MC, _RCS, 'domain_index_inject', 'Packs de dominio por turno', ':3877'),
    (_MC, _RCS, 'skill_code_prefix', 'Prefijo del código de skill', ':3898'),
    (_MC, _RCS, 'skill_command_prefix', 'Prefijo del comando slash', ':3904'),
    (_MC, _RCS, 'key_pin_length', 'Cifras del pin', ':9133'),
    (_MC, _RCS, 'key_pin_attempts', 'Intentos de pin por IP', ':9139'),
    (_MC, _RCS, 'key_pin_block_hours', 'Bloqueo de pin (horas)', ':9145'),
    (_MC, _RCS, 'log_retention_days', 'Retención del registro de actividad (días)', ':9214'),
    (_MC, _RCS, 'journal_trash_days', 'Papelera de cambios (días)', ':9226'),
    (_MC, _RCS, 'mcp_allowed_origins', 'Orígenes web de MCP', ':9551'),
    # es.po:2844-2845. El manual (línea 600) dice «Política de URL»: no está en es.po.
    (_MC, _RCS, 'url_access_policy', 'Política de acceso a URLs', ':2844'),
    # Proveedor (manual §12)
    (_MC, 'ai_provider', 'protocol', 'Protocol', ':3569'),
    (_MC, 'ai_provider', 'endpoint', 'URL del endpoint', ':3817'),
    (_MC, 'ai_provider', 'api_key', 'Clave API', ':3830'),
    (_MC, 'ai_provider', 'model_id', 'Modelo seleccionado', ':3835'),
    (_MC, 'ai_provider', 'no_external_failover', 'Sin failover externo', ':9400'),
    (_MC, 'ai_provider', 'spend_cap_usd', 'Tope mensual (USD)', ':9566'),
    (_MC, 'ai_provider', 'spend_cap_tokens', 'Tope mensual (tokens)', ':9571'),
    (_MC, 'ai_provider_role', 'use_fallback', 'Usar el respaldo', ':9952'),
    # Agente y su cadena (manual §12 y §13)
    (_MC, 'ai_agent', 'max_agent_rounds', 'Rondas LLM máx.', ':3676'),
    (_MC, 'ai_agent_provider', 'llm_idle_timeout', 'Tiempo de inactividad (s)', ':3716'),
    (_MC, 'ai_agent_provider', 'llm_round_timeout', 'Tiempo de espera por ronda (s)', ':3721'),
    (_MC, 'ai_agent_provider', 'skip_sync_fallback', 'Omitir alternativa sin streaming', ':3726'),
    # Skill y servidor externo (manual §14 y §16)
    (_MC, 'ai_skill', 'triggers', 'Disparadores', ':5908'),
    (_MC, 'ai_skill', 'is_system', 'Habilidad de sistema', ':4068'),
    (_MC, 'ai_skill', 'show_in_slash', 'Mostrar en menú slash', ':4073'),
    (_MC, 'ai_external_server', 'trusted', 'De confianza (auto-confirmar)', ':4443'),
)

# M5. Contextos de fábrica (sin dueño) por módulo y tipo. Un registro por archivo: el
# código sale del nombre o de <code>/"code" y los _es_ES tienen el suyo
# (ai_context_disk.py:545-648; context_roles.py:51-64; ai_context.py:915-929).
# pns_ai_mcp/ai/contexts: core 1, discovery 24, domain/ 26, locale/ 2 (<tipo>locale</tipo>
# en corporate_terms*.xml:5). pns_ai_chatboo/ai/contexts: domain 4, discovery 2.
M5_RECUENTO = {
    ('pns_ai_mcp', 'core'): 1,
    ('pns_ai_mcp', 'discovery'): 24,
    ('pns_ai_mcp', 'domain'): 26,
    ('pns_ai_mcp', 'locale'): 2,
    ('pns_ai_chatboo', 'domain'): 4,
    ('pns_ai_chatboo', 'discovery'): 2,
}
M5_CODIGOS_CHATBOO = ('page_tab', 'presentation_grids', 'self_chatboo', 'ui_focus',
                      'discovery_page_tab', 'discovery_page_tab_es_ES')

# M6. (código = nombre del .md, comando de «skill:» o el código, nombre)
# pns_ai_chatboo/ai/skills/system/*.md:2-3; skill_files.py:15-30. El motor no trae
# skills propias (pns_ai_mcp/ai/skills solo tiene custom/, vacía; mcp_data.xml:8-9).
M6_SKILLS = (
    ('bill_draft', 'bill-draft', 'Bill draft'),
    ('billing', 'billing', 'Billing by month'),
    ('customer_360', 'customer-360', 'Customer 360'),
    ('dashboard', 'dashboard', 'Business dashboard'),
    ('financial_health', 'financial-health', 'Financial health'),
    ('forecast', 'forecast', 'Weather forecast'),
    ('pipeline', 'pipeline', 'Sales pipeline'),
    ('sales_board', 'sales-board', 'Sales board'),
    ('top_sales', 'top-sales', 'Top sales'),
    ('users', 'users', 'Users'),
)
M6_GRUPOS_USERS = (_ADM,)  # users.md:7

# M7. pns_ai_mcp/data/ai_provider_role_data.xml:3-67 (código, accepts, respaldo);
# selección de accepts: models/ai_provider_role.py:63-76 (no hay «embedding»).
M7_ROLES = {
    'conversation': ('text', ''),
    'audio': ('audio', ''),
    'vision': ('image', ''),
    'video': ('video', ''),
    'decision': ('text', ''),
    'design': ('text', 'conversation'),
    'parser': ('text', 'conversation'),
}
M7_ACCEPTS = ('text', 'image', 'audio', 'video')

# M8. pns_ai_mcp/data/ai_agent_data.xml:8-37; pns_ai_chatboo/data/ai_agent_data.xml:7-27
M8_AGENTES = (
    ('pns_ai_mcp.ai_agent_mcp', 'pns_ai_mcp', 'endpoint'),
    ('pns_ai_mcp.ai_agent_admin', 'pns_ai_admin', 'inference'),
    ('pns_ai_chatboo.ai_agent_chatboo', 'pns_ai_chatboo', 'inference'),
)

# M9. pns_ai_chatboo/models/res_config_settings.py:96-102 (Boolean, default False);
# clave: utils/chatboo_product_icp.py:33; sin clave se lee False (:152-153).
M9_CLAVE = 'pns_ai_chatboo.allow_remote_voices'

# M10. (xmlid, xmlid del modelo, código). Todos active=True en el XML.
M10_CRONS = (
    ('pns_base.ir_cron_pns_export_purge', 'base.model_ir_attachment',
     'model._cron_purge_pns_exports()'),                       # export_purge_cron.xml:7-17
    ('pns_ai_mcp.ir_cron_ai_fetch_cache_gc', 'pns_ai_mcp.model_ai_fetch_cache',
     'model._gc_expired()'),                                   # fetch_cache_cron.xml:6-15
    ('pns_ai_mcp.ir_cron_ai_api_result_cache_gc', 'pns_ai_mcp.model_ai_api_result_cache',
     'model._gc_expired()'),                                   # api_result_cache_cron.xml:6-15
    ('pns_ai_mcp.ir_cron_ai_log_retention', 'pns_ai_mcp.model_ai_log',
     'model._cron_purge_old_logs()'),                          # ai_log_cron.xml:5-14
    ('pns_ai_mcp.ir_cron_ai_journal_trash', 'pns_ai_mcp.model_ai_change_journal',
     'model._cron_empty_journal_trash()'),                     # journal_trash_cron.xml:5-14
    ('pns_ai_mcp.ir_cron_ai_safe_operation_expire', 'pns_ai_mcp.model_ai_safe_operation',
     'model.cleanup_expired()'),                               # safe_operation_cron.xml:6-15
    ('pns_ai_chatboo.ir_cron_chatboo_async_maintenance',
     'pns_ai_chatboo.model_chatboo_async_request',
     'model.cron_maintenance()'),                              # chatboo_async_cron.xml:7-16
)

# M11. Claves que lee read_product_settings (chatboo_product_icp.py:109-155, solo
# get_param y lecturas) y lo que devuelve sin clave: (clave, campo devuelto, valor).
M11_PRODUCTO = (
    ('pns_ai_chatboo.history_retention_days', 'history_retention_days', 0),  # :124-131
    ('pns_ai_chatboo.query_data_ttl_hours', 'query_data_ttl_hours', 12),     # :30, :36, :118-123
    ('pns_ai_mcp.dataset_cache_max_bytes', 'dataset_cache_max_mb', 8),       # :29, :35, :113-117, :137-139
    ('pns_ai_chatboo.upload_max_bytes', 'upload_max_mb', 15),                # :32, :37, :46-59, :145
    ('pns_ai.download_max_bytes', 'download_max_mb', 15),                    # engine_params.py:14, :25, :113-118
    ('pns_ai.xlsx_float_decimals', 'xlsx_float_decimals', 'moneda'),         # engine_params.py:12, :95-101
)
# Otras claves numéricas del manual: solo definida/no definida y su valor si lo está.
M11_NUMERICAS = (
    'pns_ai_mcp.log_retention_days',     # res_config_settings.py:64 (manual §18: vacío)
    'pns_ai_mcp.journal_trash_days',     # change_journal.py:16-17 (30 sin clave)
    'pns_base.export_retention_hours',   # ir_attachment.py:15-16 (24 sin clave)
    'pns_ai_mcp.key_pin_length',         # key_pin.py:12, :19
    'pns_ai_mcp.key_pin_attempts',       # key_pin.py:13, :20
    'pns_ai_mcp.key_pin_block_hours',    # key_pin.py:14, :21
)
# Claves no numéricas: solo definida/no definida, nunca el valor.
M11_TEXTO = (
    'pns_ai_chatboo.show_systray',       # chatboo_product_icp.py:28
    'pns_ai_chatboo.allow_remote_voices',  # :33
    'pns_ai_mcp.url_access_policy',      # res_config_settings.py:107
    'pns_ai_mcp.mcp_allowed_origins',    # res_config_settings.py:83
    'pns_ai_mcp.domain_index_inject',    # domain_index.py:30
    'pns_ai_mcp.display_currency',       # display_currency.py:7
    'pns_ai_mcp.skill_code_prefix',      # skill_code_prefix.py:16
    'pns_ai_mcp.skill_command_prefix',   # skill_code_prefix.py:17
    'pns_ai.chart_engine',               # engine_params.py:10
    'pns_ai.default_show_mode',          # engine_params.py:11
    'pns_ai.xlsx_thousands',             # engine_params.py:13
)

# M12. Ninguna ir.rule de los tres módulos filtra por compañía: son por dueño o por
# usuario (pns_ai_mcp/security/security.xml:25-246; pns_ai_chatboo/security/security.xml:9-78;
# pns_base/security/progress_job_rules.xml:3-8).
M12_REGLAS_COMPANIA = 0
# Modelos que crean los tres módulos (clases de Model, TransientModel o AbstractModel
# con _name que no está en su _inherit; sin tests/ ni migrations/): 75 = pns_base 4,
# pns_ai_mcp 66, pns_ai_chatboo 5. Búsqueda con ast del 22/11/2026 (ninguno repetido
# entre módulos, ningún _name no literal ni con otras bases). Contra un IGUAL falso:
# con 0 modelos encontrados M12 es NO CONCLUYENTE (código 8); con otra cifra, DISTINTO.
M12_MODELOS = 75


# ---------------------------------------------------------------- lectura en Odoo

class OdooLector(object):
    """Lecturas en la BD con el Environment del cursor de solo lectura."""

    def __init__(self, env):
        self.env = env
        self._po = {}

    def _ref(self, xmlid):
        return self.env.ref(xmlid, raise_if_not_found=False)

    def _xmlid(self, rec):
        if not rec:
            return ''
        return rec.get_external_id().get(rec.id) or ''

    def _xmlids(self, recs):
        ids = recs.get_external_id()
        return set(ids.get(r.id) or '' for r in recs)

    def lang_active(self, code):
        return bool(self.env['res.lang'].search([('code', '=', code)], limit=1))

    def versions(self):
        mods = self.env['ir.module.module'].search([('name', 'in', list(MODS))])
        return dict((m.name, (m.state, m.latest_version or '')) for m in mods)

    def module_exists(self, name):
        return bool(self.env['ir.module.module'].search([('name', '=', name)], limit=1))

    def xmlids_of(self, model):
        imd = self.env['ir.model.data'].search([
            ('module', 'in', list(MODS)), ('model', '=', model)])
        return set('%s.%s' % (d.module, d.name) for d in imd)

    def record_name(self, xmlid):
        rec = self._ref(xmlid)
        return rec.name if rec else None

    def group(self, xmlid):
        g = self._ref(xmlid)
        if not g:
            return None
        return {'name': g.name, 'implied': self._xmlids(g.implied_ids),
                'category': self._xmlid(g.category_id)}

    def menu(self, xmlid):
        m = self._ref(xmlid)
        if not m:
            return None
        return {'name': m.name, 'parent': self._xmlid(m.parent_id) or '-',
                'groups': self._xmlids(m.groups_id)}

    def visible_menus(self):
        imd = self.env['ir.model.data'].search([
            ('module', 'in', list(MODS)), ('model', '=', 'ir.ui.menu')])
        names = dict((d.res_id, '%s.%s' % (d.module, d.name)) for d in imd)
        out = []
        for user in self.env['res.users'].search([('share', '=', False)], order='id'):
            visible = self.env['ir.ui.menu'].with_user(user)._visible_menu_ids()
            out.append((user.id, sorted(names[i] for i in visible if i in names)))
        return out

    def field_label(self, module, model_us, field):
        f = self._ref('%s.field_%s__%s' % (module, model_us, field))
        if not f:
            return None
        try:
            model = self.env[f.model]
        except KeyError:
            return None
        desc = model.fields_get([f.name], ['string'])
        return (desc.get(f.name) or {}).get('string')

    def po_label(self, module, model_us, field):
        if module not in self._po:
            from odoo.modules.module import get_module_path
            from odoo.tools.translate import PoFileReader
            path = os.path.join(get_module_path(module), 'i18n', 'es.po')
            self._po[module] = list(PoFileReader(path))
        # PoFileReader (odoo/tools/translate.py:652-678): por cada referencia
        # «model:<modelo>,<campo>:<módulo>.<xmlid>» da una entrada con 'name' =
        # '<modelo>,<campo>' (:671), 'imd_name' = el xmlid sin el módulo (:665, :672),
        # 'module' (:677) y 'value' = msgstr (:675). La ayuda del campo comparte xmlid,
        # por eso se exige 'name' = 'ir.model.fields,field_description'.
        want = 'field_%s__%s' % (model_us, field)
        for entry in self._po[module]:
            if (entry.get('name') == 'ir.model.fields,field_description'
                    and entry.get('imd_name') == want
                    and entry.get('module') == module):
                return entry.get('value')
        return None

    def contexts(self):
        rows = self.env['ai.context'].with_context(active_test=False).search([
            ('source_module', 'in', list(MODS)), ('owner_id', '=', False)])
        return [(r.source_module, r.context_type, r.code) for r in rows]

    def skills(self):
        rows = self.env['ai.skill'].with_context(active_test=False).search([
            ('source_module', 'in', list(MODS)), ('owner_id', '=', False)])
        return [{'module': r.source_module, 'code': r.code, 'command': r.command or '',
                 'name': r.name, 'is_system': bool(r.is_system),
                 'groups': self._xmlids(r.required_group_ids)} for r in rows]

    def roles(self):
        rows = self.env['ai.provider.role'].with_context(active_test=False).search([])
        return dict((r.code, (r.accepts, r.fallback_id.code or '')) for r in rows)

    def accepts_selection(self):
        sel = self.env['ai.provider.role']._fields['accepts'].selection
        return tuple(key for key, _label in sel)

    def agent(self, xmlid):
        a = self._ref(xmlid)
        if not a:
            return None
        return {'code': a.code, 'agent_type': a.agent_type}

    def field_meta(self, model, field):
        f = self.env[model]._fields.get(field)
        if f is None:
            return None
        default = f.default(self.env[model]) if callable(f.default) else f.default
        return {'type': f.type, 'default': default}

    def product_settings(self):
        from odoo.addons.pns_ai_chatboo.utils.chatboo_product_icp import (
            read_product_settings,
        )
        return read_product_settings(self.env)

    def param(self, key):
        rec = self.env['ir.config_parameter'].sudo().search([('key', '=', key)], limit=1)
        return (bool(rec), rec.value if rec else None)

    def currency_decimals(self):
        return self.env.company.currency_id.decimal_places

    def cron(self, xmlid):
        c = self._ref(xmlid)
        if not c:
            return None
        return {'model': self._xmlid(c.model_id), 'code': (c.code or '').strip(),
                'active': bool(c.active)}

    def company_rules(self):
        # Modelo «de los tres módulos»: el primer xmlid de su ir.model es de uno de ellos
        # (quien crea el modelo se carga antes que quien lo hereda). No se usa
        # _original_module: no aparece en el models.py del contenedor.
        primero = {}
        for d in self.env['ir.model.data'].search([('model', '=', 'ir.model')], order='id'):
            primero.setdefault(d.res_id, d.module)
        model_ids = [rid for rid, mod in primero.items() if mod in MODS]
        rules = self.env['ir.rule'].with_context(active_test=False).search([
            ('model_id', 'in', model_ids)])
        return len(model_ids), [
            (self._xmlid(r), r.model_id.model, 'company' in (r.domain_force or ''))
            for r in rules]


# ---------------------------------------------------------------- comparación

def _fmt(value):
    if isinstance(value, (set, frozenset, list, tuple)):
        return '[' + ', '.join(sorted(str(v) for v in value)) + ']'
    return str(value)


def _tipo(exc):
    """Tipo de la excepción y su SQLSTATE; nunca el mensaje."""
    name = type(exc).__name__
    code = getattr(exc, 'pgcode', None)
    if isinstance(code, str) and re.match(r'^[0-9A-Z]{5}$', code):
        return '%s (SQLSTATE %s)' % (name, code)
    return name


class _Estado(object):

    def __init__(self, out):
        self.out = out
        self.distinto = False
        self.es = False

    def linea(self, bloque, elemento, estado, detalle=''):
        if estado == DISTINTO:
            self.distinto = True
        partes = [bloque, elemento, estado]
        if detalle:
            partes.append(detalle)
        self.out(' | '.join(partes))

    def cmp(self, bloque, elemento, previsto, obtenido, nota=''):
        if isinstance(previsto, (list, tuple)) and isinstance(obtenido, (set, frozenset)):
            previsto = set(previsto)
        ok = previsto == obtenido
        detalle = nota
        if not ok:
            detalle = 'previsto: %s · obtenido: %s%s' % (
                _fmt(previsto), _fmt(obtenido), (' · ' + nota) if nota else '')
        self.linea(bloque, elemento, IGUAL if ok else DISTINTO, detalle)
        return ok

    def nombre(self, bloque, elemento, previsto, obtenido):
        if self.es:
            return self.cmp(bloque, elemento, previsto, obtenido)
        self.linea(bloque, elemento, INFORMATIVO, 'no comprobado: es_ES no está activo')
        return True


def _m1(lec, st):
    vers = lec.versions()
    ok = True
    for mod in MODS:
        state, ver = vers.get(mod, ('no instalado', ''))
        if not st.cmp('M1', mod, 'installed %s' % M1_VERSIONES[mod],
                      ('%s %s' % (state, ver)).strip()):
            ok = False
    return ok


def _m2(lec, st):
    st.cmp('M2', 'grupos de los tres módulos', set(g[0] for g in M2_GRUPOS),
           lec.xmlids_of('res.groups'))
    st.nombre('M2', M2_CATEGORIA[0] + ' nombre', M2_CATEGORIA[1],
              lec.record_name(M2_CATEGORIA[0]))
    for xmlid, es, implied in M2_GRUPOS:
        g = lec.group(xmlid)
        if g is None:
            st.linea('M2', xmlid, DISTINTO, 'no existe')
            continue
        st.nombre('M2', xmlid + ' nombre', es, g['name'])
        st.cmp('M2', xmlid + ' implica', set(implied), g['implied'])
        st.cmp('M2', xmlid + ' categoría', M2_CATEGORIA[0], g['category'])


def _m3(lec, st):
    st.cmp('M3', 'menús de los tres módulos', set(m[0] for m in M3_MENUS),
           lec.xmlids_of('ir.ui.menu'))
    for xmlid, es, padre, grupos in M3_MENUS:
        m = lec.menu(xmlid)
        if m is None:
            st.linea('M3', xmlid, DISTINTO, 'no existe')
            continue
        st.nombre('M3', xmlid + ' nombre', es, m['name'])
        st.cmp('M3', xmlid + ' padre', padre, m['parent'])
        st.cmp('M3', xmlid + ' grupos', set(grupos), m['groups'])
    # Informativo (no cuenta para el código): menús visibles de cada usuario interno.
    for uid, xmlids in lec.visible_menus():
        st.linea('M3', 'visibles uid %s' % uid, INFORMATIVO,
                 '%d: %s' % (len(xmlids), ', '.join(xmlids) or '-'))


def _m4(lec, st):
    for module, model_us, field, es, cita in M4_ETIQUETAS:
        elemento = '%s.%s__%s' % (module, model_us, field)
        if st.es:
            st.cmp('M4', elemento, es, lec.field_label(module, model_us, field))
        else:
            st.cmp('M4', elemento, es, lec.po_label(module, model_us, field),
                   nota='solo es.po')


def _m5(lec, st):
    recuento = {}
    codigos_chatboo = set()
    for mod, ctype, code in lec.contexts():
        recuento[(mod, ctype)] = recuento.get((mod, ctype), 0) + 1
        if mod == 'pns_ai_chatboo':
            codigos_chatboo.add((code or '').lower())
    for key in sorted(set(M5_RECUENTO) | set(recuento)):
        st.cmp('M5', '%s %s' % key, M5_RECUENTO.get(key, 0), recuento.get(key, 0))
    st.cmp('M5', 'códigos de pns_ai_chatboo',
           set(c.lower() for c in M5_CODIGOS_CHATBOO), codigos_chatboo)


def _m6(lec, st):
    rows = lec.skills()
    por_codigo = dict((r['code'], r) for r in rows if r['module'] == 'pns_ai_chatboo')
    st.cmp('M6', 'skills de fábrica de pns_ai_chatboo', len(M6_SKILLS), len(por_codigo))
    st.cmp('M6', 'skills de fábrica de pns_ai_mcp', 0,
           len([r for r in rows if r['module'] == 'pns_ai_mcp']))
    for code, command, name in M6_SKILLS:
        r = por_codigo.get(code)
        if r is None:
            st.linea('M6', code, DISTINTO, 'no existe')
            continue
        st.cmp('M6', code + ' comando', command, r['command'] or r['code'])
        st.cmp('M6', code + ' nombre', name, r['name'])
        st.cmp('M6', code + ' de sistema', True, r['is_system'])
    if 'users' in por_codigo:
        st.cmp('M6', 'users grupos requeridos', set(M6_GRUPOS_USERS),
               por_codigo['users']['groups'])


def _m7(lec, st):
    roles = lec.roles()
    st.cmp('M7', 'roles', set(M7_ROLES), set(roles))
    for code in sorted(M7_ROLES):
        if code in roles:
            st.cmp('M7', code + ' accepts/respaldo', M7_ROLES[code], tuple(roles[code]))
    st.cmp('M7', 'selección accepts', M7_ACCEPTS, tuple(lec.accepts_selection()))
    # Informativo, del código (no de la BD):
    st.linea('M7', 'uso de audio', INFORMATIVO,
             'solo al guardar el proveedor (ai_provider.py:301, :346, :574)')
    st.linea('M7', 'uso de vídeo', INFORMATIVO, 'ningún turno lo pide (solo selección y rol)')
    st.linea('M7', 'uso de embedding', INFORMATIVO, 'no existe en los tres módulos')


def _m8(lec, st):
    for xmlid, code, agent_type in M8_AGENTES:
        a = lec.agent(xmlid)
        if a is None:
            st.linea('M8', xmlid, DISTINTO, 'no existe')
            continue
        st.cmp('M8', xmlid + ' código/tipo', (code, agent_type), (a['code'], a['agent_type']))
    st.cmp('M8', 'módulo pns_ai_admin existe', False, lec.module_exists('pns_ai_admin'))


def _m9(lec, st):
    meta = lec.field_meta('res.config.settings', 'chatboo_allow_remote_voices')
    st.cmp('M9', 'campo tipo/por defecto', ('boolean', False),
           (meta['type'], meta['default']) if meta else None)
    definida, _valor = lec.param(M9_CLAVE)
    if definida:
        st.linea('M9', M9_CLAVE, INFORMATIVO, 'definida (no se compara ni se muestra)')
    else:
        st.cmp('M9', 'valor leído sin clave', False,
               lec.product_settings().get('allow_remote_voices'))


def _m10(lec, st):
    neutralizada = lec.param(MARCA_NEUTRALIZADA)[0]
    st.linea('M10', 'marca ' + MARCA_NEUTRALIZADA, INFORMATIVO,
             'definida: el campo activo no cuenta' if neutralizada else 'no definida')
    st.cmp('M10', 'crons de los tres módulos', set(c[0] for c in M10_CRONS),
           lec.xmlids_of('ir.cron'))
    for xmlid, model, code in M10_CRONS:
        c = lec.cron(xmlid)
        if c is None:
            st.linea('M10', xmlid, DISTINTO, 'no existe')
            continue
        st.cmp('M10', xmlid + ' modelo', model, c['model'])
        st.cmp('M10', xmlid + ' método', code, c['code'])
        if neutralizada:
            st.linea('M10', xmlid + ' activo', INFORMATIVO,
                     '%s (BD neutralizada por el kit)' % c['active'])
        else:
            st.cmp('M10', xmlid + ' activo', True, c['active'])


def _numero(valor):
    try:
        return str(int(str(valor).strip()))
    except (TypeError, ValueError):
        return None


def _m11(lec, st):
    producto = lec.product_settings()
    for key, campo, previsto in M11_PRODUCTO:
        definida, valor = lec.param(key)
        if definida:
            num = _numero(valor)
            st.linea('M11', key, INFORMATIVO, 'definida · %s = %s' % (
                campo, producto.get(campo) if num is not None else '(no numérico)'))
            continue
        if previsto == 'moneda':
            previsto = max(0, min(10, int(lec.currency_decimals())))
        st.cmp('M11', key + ' sin clave → ' + campo, previsto, producto.get(campo))
    for key in M11_NUMERICAS:
        definida, valor = lec.param(key)
        if definida:
            num = _numero(valor)
            st.linea('M11', key, INFORMATIVO,
                     'definida · valor %s' % (num if num is not None else '(no numérico)'))
        else:
            st.linea('M11', key, INFORMATIVO, 'no definida')
    for key in M11_TEXTO:
        definida = lec.param(key)[0]
        st.linea('M11', key, INFORMATIVO, 'definida' if definida else 'no definida')
    # Posible diferencia del manual (§18 y §20 dicen «Vacío»): el campo de Ajustes tiene
    # default=30 (res_config_settings.py:46-51), pero get_values pone lo que devuelve
    # read_product_settings (:111-127), 0 sin clave (chatboo_product_icp.py:124-131).
    st.linea('M11', 'retención de sesiones en Ajustes', INFORMATIVO,
             'posible diferencia del manual: en pantalla %s; el manual dice «Vacío»'
             % producto.get('history_retention_days'))


def _m12(lec, st):
    modelos, reglas = lec.company_rules()
    if not modelos:
        st.linea('M12', 'modelos de los tres módulos', NO_CONCLUYENTE,
                 'encontrados 0 · previstos %d' % M12_MODELOS)
        return False
    if not st.cmp('M12', 'modelos de los tres módulos', M12_MODELOS, modelos):
        st.linea('M12', 'reglas de compañía', INFORMATIVO,
                 'no se comparan: la cifra de modelos no coincide')
        return None
    st.cmp('M12', 'reglas de compañía', M12_REGLAS_COMPANIA,
           len([r for r in reglas if r[2]]))
    st.linea('M12', 'reglas en los modelos de los tres módulos', INFORMATIVO,
             str(len(reglas)))


BLOQUES = (
    ('M1', _m1), ('M2', _m2), ('M3', _m3), ('M4', _m4), ('M5', _m5), ('M6', _m6),
    ('M7', _m7), ('M8', _m8), ('M9', _m9), ('M10', _m10), ('M11', _m11), ('M12', _m12),
)


# ---------------------------------------------------------------- ejecución

def _solo_lectura(cr):
    cr.execute('SHOW transaction_read_only')
    row = cr.fetchone()
    return bool(row) and row[0] == 'on'


def _ejecutar(cr, out, Environment, uid, factory):
    st = _Estado(out)
    try:
        cr.execute('SET TRANSACTION READ ONLY')
        if not _solo_lectura(cr):
            out('PREPARACIÓN | transacción de solo lectura | ERROR | SHOW no devuelve «on»')
            for nombre, _fn in BLOQUES:
                out('%s | %s' % (nombre, NO_EJECUTADO))
            return COD_ERROR
        env0 = Environment(cr, uid, {})
        st.es = bool(factory(env0).lang_active('es_ES'))
        env = Environment(cr, uid, {'lang': 'es_ES'}) if st.es else env0
        lec = factory(env)
    except Exception as exc:
        out('PREPARACIÓN | %s | %s' % (ERROR, _tipo(exc)))
        for nombre, _fn in BLOQUES:
            out('%s | %s' % (nombre, NO_EJECUTADO))
        return COD_ERROR
    out('PREPARACIÓN | es_ES activo | %s' % (
        'sí' if st.es else 'no: las etiquetas de M4 salen «solo es.po»'))

    error = False
    concluyente = True
    for nombre, fn in BLOQUES:
        if error:
            out('%s | %s' % (nombre, NO_EJECUTADO))
            continue
        if not concluyente:
            out('%s | %s' % (nombre, NO_CONCLUYENTE))
            continue
        try:
            if not _solo_lectura(cr):
                out('%s | %s | transacción no de solo lectura' % (nombre, ERROR))
                error = True
                continue
            resultado = fn(lec, st)
        except Exception as exc:
            out('%s | %s | %s' % (nombre, ERROR, _tipo(exc)))
            error = True
            continue
        # False = no concluyente: M1 (BD no actualizada; el resto no se ejecuta) o
        # M12 (ningún modelo de los tres módulos).
        if resultado is False:
            concluyente = False
    # Orden de los códigos: 20 > 8 > 1 > 0.
    if error:
        return COD_ERROR
    if not concluyente:
        return COD_NO_CONCLUYENTE
    return COD_DISTINTO if st.distinto else COD_OK


def run(env, out, _lector=None):
    """Ejecuta M1 a M12 con un cursor nuevo de solo lectura y devuelve el código."""
    from odoo import SUPERUSER_ID, api
    factory = _lector or OdooLector
    codigo = COD_ERROR
    try:
        cr = env.registry.cursor()
    except Exception as exc:
        out('PREPARACIÓN | cursor | %s | %s' % (ERROR, _tipo(exc)))
        out('CÓDIGO: %d' % COD_ERROR)
        return COD_ERROR
    try:
        codigo = _ejecutar(cr, out, api.Environment, SUPERUSER_ID, factory)
    except Exception as exc:
        out('PREPARACIÓN | interno | %s | %s' % (ERROR, _tipo(exc)))
        codigo = COD_ERROR
    finally:
        try:
            cr.rollback()
        except Exception as exc:
            out('FINAL | rollback | %s | %s' % (ERROR, _tipo(exc)))
            codigo = COD_ERROR
        try:
            cr.close()
        except Exception as exc:
            out('FINAL | close | %s | %s' % (ERROR, _tipo(exc)))
            codigo = COD_ERROR
    out('CÓDIGO: %d' % codigo)
    return codigo


if __name__ == '__main__' and 'env' in globals():
    sys.exit(run(env, print))  # noqa: F821 (env lo pone el shell de Odoo)
