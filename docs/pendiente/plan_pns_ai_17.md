# Plan: módulos IA `pns_ai` en Odoo 17.0

- **Rama de trabajo:** `17.0-pns-ai`, desde `17.0` en `95110bd` (configuración de claude-odoo-kit). Primer commit: la
  base del fabricante sin cambios. A `17.0` solo llega con merge commit cuando esté corregida y validada (como en 14.0).
- **Estado (23/11/2026):** base copiada; empieza la fase 0.

## Decisiones (Sergio, 22 y 23/11/2026)

1. **Base:** la versión actual de la rama 17.0 del fabricante (descargada el 23/11/2026), no la entrega `pns_o19` del
   22/10/2026.
2. **Destino:** la rama `17.0` de `third_party`, para todos los clientes de Odoo 17 que lo soliciten.
3. **Módulos anteriores retirados de `17.0`:** `pns_base` 1.2.20, `pns_ai_mcp` 3.1.486 y `pns_ai_chatboo` 2.1.322
   (subidos el 02/09/2026, `a5abdea` a `4e1ebcc`). No estaban instalados en ninguna BD: ni en producción ni en staging
   (Sergio) ni en las 5 BD locales de la 17 (comprobado el 23/11/2026). Retirada: PR #5, merge `dff50b4`. Su historial,
   incluida la adaptación de `4e1ebcc` («adapt to odoo 17»), sigue en git.
4. **Configuración del kit en `17.0`:** `95110bd` (`configurar_repo.py --version 17 --tipo comun`).

## Origen de la base

Descargada por Sergio de GitHub (rama 17.0) el 23/11/2026 a las 09:56. Copia de referencia, fuera del repo:
`/home/soporte/pns_fabricante/17.0_17.0.3.1.996` (con `ORIGEN.txt`).

| Módulo | Versión | Repo | Commit | SHA-256 del zip |
|---|---|---|---|---|
| `pns_base` | 17.0.1.2.92 | `patanegra-soft/pns_base` | `9272e5d40426fc14a53dd8031d0f8954ca5c3dd3` | `a41d02d17071327737fbdaca51fe33207682b109be5a572de0dc5ee3f11b0c20` |
| `pns_ai_mcp` | 17.0.3.1.996 | `patanegra-soft/pns_ai_mcp` | `1f63e0a2f372ded02e3f6bb53a458992817d3465` | `ebddd7484ceabc1d19edd4b6dd9f13722e97554f533ea92c066f22e08763a4d8` |
| `pns_ai_chatboo` | 17.0.2.1.597 | `patanegra-soft/pns_ai_chatboo` | `48a1e92a224a3d92f917898e7a9480dc578216bf` | `58275a3e9ed8428dc0305be373c70fcb0efebba812e43a3667375d93b3100bd1` |

Referencia de la 14 para comparar: `/home/soporte/pns_fabricante/3.1.973` (1.2.69, 3.1.973 y 2.1.587).

## Plan

1. **Fase 0, viabilidad:**
   - comparar 17.0.3.1.996 con 3.1.973 (14), separando lo que cambia de versión de lo que cambia de serie;
   - ver qué parches de la rama `14.0-pns-ai-3973` siguen haciendo falta y cuáles se pueden portar (comparación con
     3.1.973, §8.2: 24 de 25 tocan código común; el 20 hay que rehacerlo en owl2; el 18 y el 24 dependen de `res_users`
     de la 17);
   - instalar los tres módulos en un laboratorio de la 17 (`odoo-dev 17 paridad` antes; librerías `openpyxl`,
     `reportlab` y `requests`) y pasar los tests del fabricante;
   - consultar al fabricante el soporte oficial de la 17.
2. **Fase 1:** analizar el código que solo se activa en la 15 o superior y que en la 14 no se revisó
   (`ir_ui_view_patch.py`, assets, rutas JSON, cliente de Chatboo), con el criterio de los PNS.
3. **Fase 2:** portar y aplicar los parches en esta rama, con sus tests.
4. **Fase 3:** staging en la 17, cliente y merge commit en `17.0`.

## Abierto

- **Una sola copia de trabajo:** el laboratorio de la 14 y el de la 17 montan `third_party` según la rama activa; hay
  que decidir cómo trabajar con los dos a la vez.
- **Versiones:** la 17.0 del fabricante (3.1.996) es posterior a la base de la 14 (3.1.973). Falta mirar si su rama
  14.0 también está en 3.1.996.
- **Manifiestos:** los del fabricante llevan el prefijo `17.0.`; los retirados no lo llevaban.
- **`4e1ebcc`:** comprobar si la base nueva ya incluye lo que adaptaba (`ir_ui_view_patch.py`, `security_groups.xml`).

## Documentos de la 14 (rama `14.0`)

`docs/specs/comparacion_pns_ai_3-1-973.md` (§8.2), `docs/specs/analisis_pns_base.md` (§2.3),
`docs/pendiente/parches_pns_ai.md` («Índice de la rama 14.0-pns-ai-3973»), `docs/pendiente/pns_ai_decisiones.md` (N15).
