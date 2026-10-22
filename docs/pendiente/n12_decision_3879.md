# N12 a la vista de 3.1.879: datos para decidir

- **Fecha:** 22/10/2026.
- **Decide:** Sergio (si hace falta, con el jefe). Este documento reúne hechos y da una recomendación
  marcada como tal; no decide.
- **Fuentes:** [comparación con 3.1.879](../specs/comparacion_pns_ai_3-1-879.md) (pasadas A y B,
  verificada por `odoo-reviewer` el 22/10) y [N12 en pns_ai_decisiones.md](pns_ai_decisiones.md).
- **Ojo con las letras:** aquí se usan las de N12 en `pns_ai_decisiones.md`. En §10 de la comparación van
  al revés: su «(a)» es la **b)** de N12 (mantener 3.1.782) y su «(b)» es la **a)** (reaplicar sobre
  3.1.879).

## 1. Situación de partida

- **Decisión vigente (20/10/2026): b) con vigilancia.** La 3.1.782 es la base propia de Seges. Las
  versiones nuevas del fabricante no entran en el repo: se comparan fuera solo para traer
  **correcciones de seguridad** como parches de Seges. Motivo: cada versión añade funciones (y hallazgos
  nuevos).
- **Rama:** `14.0-pns-ai-correcciones`, con los parches 1 a 12 (E0 a E2). Pendientes: ET (en pausa),
  E3, E4, E5 y «Después».
- **LIYBEN:** 3.1.782 con los parches 1 a 6, instalada el 16/10 (poco historial). Recibe las
  correcciones de una vez al final del plan.

## 2. Qué ha cambiado desde el 20/10

1. **El fabricante ha corregido mucho de lo que teníamos pendiente.** En 3.1.879 están VERIFICADAS o
   mejor que en la rama unas 20 fichas de §4 que en nuestro plan eran E4 o «Después» (PNS-92, 30, 37,
   89, 28, 33, 20, 60, 65, 35, 55, 66, 62, 16, 59, 86, 22, 40, obs. 2, 3 y 8). Cubre por código buena
   parte de E5 (PNS-94). Su sandbox es mejor que nuestros parches 7 a 9: bloquea todo nombre con `_` en
   las dos capas y cierra el alias D-2. D9 y PB-2 reducen mucho su alcance (comparación §1.2, §2, §5.7,
   §10.2).
2. **Y ha añadido superficie con agujeros nuevos:**
   - **Alta:** M13 (`unlink_retired_from_module`, también portal), `collect_pin` (PNS-83) y la papelera
     del diario (PNS-37).
   - **Media:** lienzo (M1, M2, F1).
   - **Requieren prueba:** la revisión previa de importación (PNS-20) y Chart.js 4 en `window.Chart`
     (PNS-70).

   Ver comparación §3, §6.1 y §8.
3. **M10 es Crítica y está en las dos opciones.** Un AI Administrator ejecuta un plan con la identidad
   de otro usuario. En la rama se da `base.group_system`, porque el parche 12 mira al usuario
   suplantado. Hay que corregirlo **decida lo que se decida**. M11, M12, PNS-97, PNS-98 y los
   `commit()` de la Caja B también están en las dos (comparación §8.7, §10.2).
4. **«Vigilar y traer solo la seguridad» sale caro.** El motor está reorganizado (unas 62.000 líneas de
   diff; `engine_*`, `validators_*`, `relaxaicode_*`). Las correcciones de 3.1.879 no son parches
   pequeños que se puedan traer uno a uno: el bloqueo de `_` del sandbox, por ejemplo, es transversal.
   Con b), lo razonable es reimplementar a nuestra manera, no traer.
5. **Actualizar no es reversible sin copia.** El `-u` borra `ai_log.agent_id` y las columnas del PIN,
   reescribe el historial de Chatboo y renombra cinco parámetros (comparación §9). En LIYBEN hay poco
   historial (desde el 16/10).
6. **Odoo 17.** El fabricante ya entrega la versión 19. Una base cercana a la suya acorta la futura fase
   de viabilidad de la 17; una base 3.1.782 propia la aleja.

## 3. Opciones

| | **b) Mantener 3.1.782** (vigente) | **b′) Cambiar una vez de base a 3.1.879 y mantenerla** | **a) / c) Reaplicar en cada versión** |
|---|---|---|---|
| Qué es | Seguir con la rama actual | Rama nueva desde `14.0` con 3.1.879 y los parches de Seges; a partir de ahí, igual que b) (vigilancia, sin traer versiones) | Importar cada versión intacta y reaplicar parches; c) con criterio de salida hacia b) |
| Parches 1 a 9 | Permanentes | Desaparecen | Desaparecen |
| Parches 10 a 12 | Siguen; el 12 hay que ampliarlo por M10 | Se adaptan: 10, renombrar `collect_pin`; 11, el `unlink`; 12, criterio + vía CRUD + M10 | Igual que b′, en cada versión |
| Trabajo de corrección | ET, E3, E4, E5 y «Después» (~20 fichas que el fabricante ya hizo) + lo común | Lo común + restos de 3.1.879: Críticas PNS-54 y 07 (también abiertas con b); Altas M13, PNS-37, 19, 17, 82 y `collect_pin`; Medias M1, M2, F1… (comparación §10.2) | Lo de b′ y, en cada versión, una comparación como esta |
| Superficie nueva | Ninguna | Lienzo, papelera, topes, revisión previa… (con sus restos) | La de cada versión |
| Coste de actualizar LIYBEN y `pns_demo` | Ninguno | Un `-u` con copia previa y las pérdidas de §9 | En cada versión |
| Tests | Los de E1/E2 siguen valiendo | Adaptar `test_seges_*` (importación rota); Chatboo sin tests del fabricante | Ídem, en cada versión |
| Odoo 17 | Base alejada de la del fabricante | Base cercana | Base al día |
| Incertidumbre | Conocida (ya en staging y LIYBEN) | 62.000 líneas nuevas, solo revisadas estáticamente; los `unit_tests/` no vienen | La mayor |

- **b′ no estaba en N12.** Es una variante de b): se toma la base nueva una sola vez y se vuelve a
  congelar. Recoge el motivo del 20/10 (no ir detrás de cada versión) sin renunciar a lo ya corregido.

## 4. Lo que hay que hacer en cualquier caso

- **M10** en la rama actual: LIYBEN y `pns_demo` lo tienen. Antes, la comprobación de LIYBEN (§6) dice
  si hoy es explotable allí.
- **Archivar los 18 usuarios de portal de LIYBEN** (decidido el 20/10): cierra M11 para portal, y M13 si
  se pasa a 3.1.879.
- **Aviso al fabricante:** al final, con todo (decisión de Sergio del 22/10).

## 5. Recomendación (Claude; la decisión es de Sergio)

**b′, condicionada a la fase 3 en laboratorio.**

**Por qué:**
- Lo que el fabricante ha corregido (unas 20 fichas, el sandbox y buena parte de E5) es más que lo que
  ha abierto.
- Los agujeros nuevos más graves se cierran con cambios pequeños y localizados: comprobar acceso en
  M13, renombrar `collect_pin` o comprobar el dueño en M1.
- M10 hay que hacerlo igualmente.
- Con b) habría que reimplementar esas 20 correcciones sobre un motor que el fabricante ya no mantiene.
- Congelar después de cambiar mantiene el motivo de la decisión del 20/10.

**Condiciones para seguir con b′.** Si alguna falla, volver a b):
1. `odoo-dev 14 paridad pns_base,pns_ai_mcp,pns_ai_chatboo` sin módulos que no se importan.
2. Tests del fabricante de `pns_ai_mcp` sin regresiones graves frente a la línea base de 3.1.782.
3. P-6 ampliada (sin bloqueos de sesión) y P-70 (gráficos de Odoo intactos con Chatboo abierto).
4. P-9a, P-9b y P-9e sobre una copia de `pns_demo`: las pérdidas son las de §9 y nada más.

**Contra:**
- Se cambia código revisado y probado en staging por código revisado solo leyendo.
- Chatboo no trae tests.
- Hay que repetir en laboratorio y staging parte de lo ya validado.

## 6. Comprobación previa en LIYBEN (solo lectura)

AI Administrator activos que no son administradores de Ajustes (los únicos para los que M10 añade
privilegio):

```sql
SELECT u.id, u.login
FROM res_users u
JOIN res_groups_users_rel r ON r.uid = u.id
JOIN ir_model_data d ON d.res_id = r.gid AND d.model = 'res.groups'
     AND d.module = 'pns_ai_mcp' AND d.name = 'group_ai_admin'
WHERE u.active
  AND u.id NOT IN (
    SELECT r2.uid FROM res_groups_users_rel r2
    JOIN ir_model_data d2 ON d2.res_id = r2.gid AND d2.model = 'res.groups'
         AND d2.module = 'base' AND d2.name = 'group_system');
```

- **0 filas:** M10 no es explotable hoy en LIYBEN.
- **Alguna fila:** quitarle el grupo de IA hasta corregir M10.

## 7. Siguientes pasos según la decisión

| Decisión | Pasos |
|---|---|
| **b) Mantener** | Parche 13 (M10) en la rama, ampliando el criterio del 12; P-8b, P-8f y P-8g sobre la rama; retomar ET; registrar M10, M11 y M12 con número PNS en el seguimiento; borrar `_fabricante/` |
| **b′) Cambiar una vez** | 1. Fase 3 en laboratorio (BD nueva, fuera de `pns_demo`): paridad, tests del fabricante, `test_seges_*` adaptados, P-6 ampliada, P-70, P-8a y P-8b. 2. Si pasa: rama `14.0-pns-ai-3879` desde `14.0`, plan nuevo (parches 10-12 adaptados, M10, M13, `collect_pin`, papelera, restos Críticos y Altos) y decidir qué hacer con el lienzo. 3. P-9 sobre copia de `pns_demo`. 4. Staging y, al final, LIYBEN con copia completa previa. 5. Conservar `_fabricante/3.1.879` hasta tener la rama |
| **a) / c) Reaplicar** | Como b′, más el procedimiento de comparación por versión en `parches_pns_ai.md` |

**En cualquier caso**, actualizar N12 en `pns_ai_decisiones.md` con un bloque «Tras la versión 3.1.879
(22/10/2026)» que remita a este documento, y hacer commit `[DOC]` de la comparación.

## 8. Decisiones que quedan abiertas tras N12

- Criterio de grupos:
  - el de Seges, parche 12: Ajustes para cualquier grupo;
  - o el del fabricante: cúspide cerrada para todos y el resto libre.
- Si se elige b′, el lienzo (Canvas):
  - corregir M1, M2 y F1;
  - o dejarlo sin proveedor de diseño. Si esto basta para cerrarlo, REQUIERE PRUEBA: `page_html` no
    parece necesitarlo.
- Pedir al fabricante el commit de `pns_base` 1.2.47 y los `unit_tests/`: barato, y aclara numeración y
  pruebas.
