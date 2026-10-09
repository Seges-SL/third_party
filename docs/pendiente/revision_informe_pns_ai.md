# Revisión de exactitud del informe para el fabricante (pns_ai)

- Fecha: 2026-10-09
- Rama: 14.0-analisis-pns-ai
- Documento revisado: `docs/pendiente/informe_fabricante_pns_ai.md`
- Contrastado con: `docs/pendiente/verificacion_seguridad_pns_ai.md`, el código local de
  `pns_base`, `pns_ai_mcp` y `pns_ai_chatboo`, y el core de referencia en `/opt/odoo-src/14.0/`.
- Método: lo revisó el agente `odoo-reviewer`, que solo leyó código: no arrancó Odoo ni
  reprodujo ningún ataque. Los puntos de PNS-22, PNS-26 y §7.2 se han vuelto a comprobar
  aparte y se confirman.

**Veredicto global: el informe necesita 9 correcciones antes de enviarlo.** Ningún hallazgo es
falso. Hay uno con la gravedad inflada (PNS-22). Hay un estado "Reproducido" que no se sostiene
(§7.2). En otros tres hallazgos (PNS-04, 05 y 57) el código no dice exactamente lo que cuenta
el texto.

## Hallazgos de gravedad Crítica y Alta

| PNS | Veredicto | Nota |
|---|---|---|
| 01 | CORRECTO CON MATIZ | El fallo existe (`ai_system_action.py:715-716`, `:677` usa `sudo()`, `compat.py:113-116`). Pero la causa no es que sea un `AbstractModel`: `call_kw` no comprueba nunca el ACL del modelo (core `web/controllers/main.py:1360-1362` y `odoo/api.py:395-409`). PNS-11 lo demuestra en un modelo normal. |
| 02 | CORRECTO | Líneas exactas. El estado "parcial" coincide con la prueba B. |
| 03 | CORRECTO | `readonly=True` no protege en `write`: el core solo mira el ACL y la regla sobre el estado anterior (`models.py:3593-3595`). Coincide con la prueba D. |
| 04 | CORRECTO CON MATIZ | Con `confirmed_uid=1` Odoo activa `su=True` (`api.py:450-451`). Aun así, `check_safe_plan_permissions` y `user_has_required_groups` miran por SQL los grupos de ese uid, y uid 1 no es AI Writer, así que el plan fallaría. El ataque real es usar el uid de un administrador que sea AI Admin. Sigue siendo Crítica. |
| 05 | CORRECTO CON MATIZ | No lo hace "cualquier usuario del chat": hace falta tener los grupos que pide el plan (AI Writer para CRUD). Ese usuario lo ejecuta con `su=True`, sin ACL ni reglas. |
| 06, 07 | CORRECTO | Líneas exactas. |
| 08–21 | CORRECTO | En PNS-15 el XSS no es solo contra uno mismo: en Odoo 14 los modelos transitorios no tienen regla implícita de creador. |
| 22 | **SOBREESTIMADO** | Por MCP, `clean_system` sí exige AI Writer (`tools_system.py:51` → `_get_env_for_operation('write')`). Solo queda sin control por el `DummyController` (`utils/agent_engine.py:3381-3386`). Además, el borrado usa el entorno del usuario, y el core solo deja borrar `ir.actions.act_window` a `group_system`. Pasa a ser defensa en profundidad, de gravedad **Media**. |
| 23–25, 27 | CORRECTO | En PNS-27 los CVE no se han podido comprobar sin conexión. |
| 26 | **LÍNEAS DESPLAZADAS** | La línea `:1171` hace commit sobre un cursor propio (abierto en `:1134`). Los commits sobre el cursor del llamador son `:1231, 1337, 1380, 1684`. |
| 53 | CORRECTO | La escritura en la sesión de otro usuario está reproducida (fase 2 §3). |
| 54 | CORRECTO | Falta citar la ruta `/pending` en `verification_ui.py:108-109`. |
| 55, 56, 58–60 | CORRECTO | En PNS-60 la función se llama `escapeHtml`, no `_escapeHtml`. |
| 57 | CORRECTO CON MATIZ | El motor se ejecuta con el uid de quien llama a `spawn()` (`:232, 252`), no con el `user_id` del registro. El impacto se mantiene. |

## Gravedad Media y Baja (solo archivo:línea)

- **Correctos:** todos menos los cuatro de abajo.
- **PNS-41:** falta citar dónde se crea el iframe, `pns_base/static/src/js/pns_module_index.js:17-19`.
- **PNS-44:** el aviso no sale de `:90`; sale de `:41-44` y `:93`, a través de `get_module_path` (core `modules/module.py:220`).
- **PNS-74:** el texto nombra elementos sin línea: `chatboo_component_v2.js:628, 643, 4850` y `chatboo_systray.js:38-49, 190`.
- **PNS-62 y PNS-65:** solo matices de rango, sin efecto en el hallazgo.

## Otros apartados

- **§7.1, §7.3, §7.4 y §8.5:** correctos.
- **§7.2: ESTADO INCORRECTO.** El razonamiento es bueno: el core no ejecuta carpetas de
  migración con ese formato de versión (`migration.py:108-111, 161`). Pero la "reproducción" no
  prueba nada. En el laboratorio el módulo se instaló y se actualizó con la misma versión
  (3.1.486), y en ese caso no se ejecuta ningún script, tengan el formato que tengan.

## Correcciones al informe

1. **§1.6 y PNS-01:** cambiar la causa. Debe decir que "`call_kw` no comprueba el ACL del modelo; solo lo hacen los métodos ORM, y estos métodos usan `sudo()`", en lugar de atribuirlo a que sea un `AbstractModel`.
2. **PNS-04:** sustituir el ejemplo `confirmed_uid=1` por "el uid de un usuario que tenga los grupos de IA del plan". Añadir que el caso con uid 1 requiere prueba.
3. **PNS-05 y la frase relacionada de PNS-03:** "un usuario con los grupos que exige el plan lo ejecuta con `su=True`, sin ACL ni reglas", en lugar de "cualquier usuario del chat… como superusuario".
4. **PNS-22:** bajarlo a Media y redactarlo como defensa en profundidad (`is_write` no se aplica de forma centralizada; la puerta falta en el `DummyController`).
5. **PNS-26:** cambiar las líneas a `mcp_safe_operation.py:1231, 1337, 1380, 1684`.
6. **§7.2:** cambiar el estado a "Verificado en código" y quitar la afirmación sobre el registro de Odoo. Ajustar también la línea 35, §1.2 y §1.10, que lo dan por reproducido. Para reproducirlo de verdad habría que instalar 3.1.483 y actualizar a 3.1.486. Conviene añadir esta salvedad en `verificacion_seguridad_pns_ai.md`, fase 2 §6.
7. **PNS-57:** el motor se ejecuta "con el uid de quien lo invoca", no "con el uid del registro".
8. **PNS-54:** añadir `verification_ui.py:108-109`.
9. **Ubicaciones menores:** las de PNS-41, 44, 60 y 74 de la sección anterior. En §1.8, "lee ambas cachés" debe ser "tiene acceso de lectura a ambas cachés", porque en la prueba estaban vacías.

## Posibles problemas que no están en el informe

El revisor vio además dos posibles problemas. Ninguno se ha probado; queda por decidir si se
incluyen:

- **`main.py:660` (PNS-13):** si la sesión no tiene `mcp_user_id`, la petición se ejecuta como `SUPERUSER_ID`.
- **`read_progress` (PNS-55):** por el mismo mecanismo de PNS-01, probablemente también puede llamarlo un usuario de portal. Contradiría §1.9, que dice que el portal no accede. Requiere prueba.
