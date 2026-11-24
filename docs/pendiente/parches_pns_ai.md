# Parches de Seges en los módulos pns_ai (Odoo 17)

- **Rama:** `17.0-pns-ai` (fase 2 de `docs/pendiente/plan_pns_ai_17.md`; tandas y registro de cada una en
  `docs/pendiente/fase2_pns_ai_17_3996.md`). A `17.0` llega al final de la fase 3, con PR y merge commit
  (decisión 114).
- **Base del fabricante (R17):** `pns_base` 17.0.1.2.92, `pns_ai_mcp` 17.0.3.1.996 y `pns_ai_chatboo`
  17.0.2.1.597. No se tocan `version`, `depends`, `external_dependencies` ni `i18n`, y no se añade `migrations/`
  (decisión 115).
- **Registro corto (decisión 119):** número, id, tanda, estado y commit. El detalle de cada parche (problema,
  cambio, test y neutralización) está en `14.0:docs/pendiente/parches_pns_ai.md`, con el mismo número; lo propio
  de la 17 (adaptación, citas y resultados), en el registro de su tanda.
- **Creado:** 24/11/2026, en la tanda T0.

## Marcadores

Junto a cada cambio, como en la 14:

```
# Seges: parche N (<id>, <tipo>). Ver docs/pendiente/parches_pns_ai.md
```

`<id>` es el PNS o el id de la 14 (`M1`, `F1`…); `<tipo>`, `seguridad`, `robustez`, `compatibilidad`,
`funcional` o `datos`; en JS, `// …`, y en XML, `<!-- … -->`. Las correcciones de la fase 1 llevan su número
desde el 40 y su F1-n como id (decisión 120). `F1` (27 y 29) es el hallazgo F1 de la revisión E3′ de la 14;
`F1-n`, desde el 40, son los de `fase1_pns_ai_17_3996.md`, sección 5 (decisión 148): en `grep`, `(F1,` y `(F1-`
no se confunden. Los tests de Seges van en `tests/test_seges_*.py`, con el bloque de Seges al final de
`tests/__init__.py`. Listado:

```sh
grep -rn "Seges: parche" pns_base pns_ai_mcp pns_ai_chatboo
```

## Índice

Los parches 1 a 6 eran de la base 3.1.782 de la 14 y se retiraron en el cambio a 3.1.879 (los cubre el
fabricante). De los demás:

| N.º | id | Tanda | Estado | Commit |
|---|---|---|---|---|
| 7 | PNS-90 | T0 (test) | Retirado en 3.1.879 (cubierto por el fabricante); no regresión | — |
| 8 | PNS-91 | T0 (test) | Retirado en 3.1.879 (cubierto por el fabricante); no regresión | — |
| 9 | PNS-85 | T0 (test) | Retirado en 3.1.879 (cubierto por el fabricante); no regresión | — |
| 10 | PNS-83 | T0 (test) | Retirado en 3.1.973 (cubierto por el fabricante); no regresión | — |
| 11 | PNS-82 | T5a | Pendiente | — |
| 12 | PNS-01, PNS-02 | T1 | Validado en el laboratorio (con `test_system_action.py`, decisión 140) | `f70c3c0` |
| 13 | M10 | T0 (test) | Retirado en 3.1.973 (cubierto por el fabricante); no regresión | — |
| 14 | M13 | T0 (test) | Retirado en 3.1.973 (cubierto por el fabricante); no regresión | — |
| 15 | PNS-07 | T4 | Pendiente | — |
| 16 | PNS-54 | T1 | Validado en el laboratorio | `f70c3c0` |
| 17 | PNS-37 | T1 | Validado en el laboratorio | `f70c3c0` |
| 18 | PNS-19 | T3 | Pendiente: O1 ampliado con B2 y P-22, sin B | — |
| 19 | PNS-17 | T1 | Validado en el laboratorio | `f70c3c0` |
| 20 | PNS-70 | T6 | Pendiente | — |
| 21 | PNS-20 | T2 | Validado en el laboratorio | `b391159` |
| 22 | PNS-100 | T4 | Pendiente | — |
| 23 | PNS-101 | T0 (test) | Retirado en 3.1.973 (cubierto por el fabricante); no regresión | — |
| 24 | PNS-102 | T3 | Pendiente | — |
| 25 | M1 | T5a | Pendiente | — |
| 26 | M2 | T5a | Pendiente | — |
| 27 | F1 | T5b | Pendiente | — |
| 28 | D1 | T5a | Pendiente | — |
| 29 | F1 (P-8e a) | T5b | Pendiente | — |
| 30 | M11 | T0 (test) | Retirado en 3.1.973 (cubierto por el fabricante); no regresión | — |
| 31 | M12 | T0 (test) | Retirado en 3.1.973 (cubierto por el fabricante); no regresión | — |
| 32 | PNS-97 | T1 | Validado en el laboratorio | `f70c3c0` |
| 33 | PNS-29 | T1 | Validado en el laboratorio | `f70c3c0` |
| 34 | PNS-96 | T5b | Pendiente | — |
| 35 | PNS-109 (NUEVO-2) | — | No aplica: migración atada a 14.0.3.1.973 | — |
| 36 | PNS-103 | T2 | Validado en el laboratorio | `b391159` |
| 37 | PNS-104 | — | No aplica: cada cursor tiene su `Transaction` en la 17 | — |
| 38 | PNS-105 | — | No aplica: la misma causa que el 37 | — |
| 39 | PNS-107 | T4 | Pendiente | — |

- **Estados:** Pendiente → Aplicado → Validado en el laboratorio → Validado en staging. Además, «Retirado» (lo
  cubre el fabricante) y «No aplica» (clasificación, secciones 5 y 6, y su sección 11, punto 5).
- **Commit:** el `[FIX]` de la tanda (el `[ADD]` de los tests y el `[DOC]` del registro, en el registro de la
  tanda). En los retirados, «—»: sus tests de no regresión van en el `[ADD]` de T0.
- **«T0 (test)»:** el test de la 14 se conserva como no regresión de la corrección del fabricante (decisión 116).

## Tests sin parche (T0)

| Test | Módulo | Archivo | Qué cubre |
|---|---|---|---|
| E0′ | `pns_ai_chatboo` | `test_seges_chatboo_smoke.py` | esqueleto de los tests de Chatboo |
| Anexo de PNS-26 | `pns_ai_mcp` | `test_seges_verify_execute_40001.py` | `verification/execute`; 2 casos con `skip` |

## Correcciones de la fase 1 (desde el 40)

Reciben número al portarse, uno por corrección y en el orden de las tandas, con su F1-n como id (decisión 120).
Pendientes: caso 24 (T3), F1-6, SSE sin escapar y creador en `session_file` (T7), F1-7 y `str(e)`
del Chatboo (T8), F1-8 (T9) y F1-9 a F1-12 (T10).

| N.º | id | Tanda | Estado | Commit |
|---|---|---|---|---|
| 40 | F1-2 | T1 | Validado en el laboratorio | `f70c3c0` |
