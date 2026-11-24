# Plan: módulos IA `pns_ai` en Odoo 17.0

- **Rama de trabajo:** `17.0-pns-ai`, desde `17.0` en `95110bd` (configuración de claude-odoo-kit). Primer commit: la
  base del fabricante sin cambios. A `17.0` solo llega con merge commit cuando esté corregida y validada (como en 14.0).
- **Estado (24/11/2026):** base copiada; fases 0 y 1 hechas. Clasificación de los parches en
  `docs/pendiente/clasificacion_parches_pns_ai_17_3996.md`; laboratorio `lab_pns_ai_3996` montado, con imagen propia
  con Chrome: los tres módulos se instalan y pasan los 249 tests del fabricante, el del navegador incluido (3 omitidos
  por el entorno; sección 10 de la clasificación). Sección 8 cerrada (resultados en la sección 11):
  - punto 8, citas del core: 51, 45 iguales y 6 desplazadas, ninguna distinta ni ausente (`cd3192f`);
  - punto 2, parche 20 (`window.Chart`): confirmado (`dbca83c`);
  - puntos 3 y 4, parches 21 y 36 (revisión de importación y vistas sin Ajustes): confirmados (`2eda904`);
  - punto 5, parches 37 y 38 (cursores aparte): no aplican, no se portan (`67bb15b`);
  - punto 1, parche 18 (caché de secretos en la caja A): (a) sin invalidación B, (b) y (c) confirmados; se porta como
    O1 ampliado (decisión 29, `59a4662`);
  - punto 7, parches 22 y 39 (métodos con efectos): las listas se actualizan en el port; salen 6, entran 13 en la
    lista global y en la tabla por modelo y 6 solo en la tabla (`b7c09b8`);
  - punto 6, parche 29: sus tests, en la fase 2 del plan (la predicción está en la sección 11);
  - laboratorio (`seges_pruebas_3996`, copia en `docs/pendiente/lab_3996/`): `13 failed, 0 error(s) of 30 tests`, los
    13 `[HYPOTHESIS]` esperados de los puntos 2, 3, 4 y 1, que pasan a verde con el port;
  - pendiente para el port, en la sección 11: las aperturas de cursor del punto 5 localizadas y no leídas, la caja A
    con uid 1 (decisión 48) y el alias de los parches 15 y 22 (E3).

  Fase 1 hecha (24/11/2026; de `ac624f9` a `8e5100d` y el commit del cierre), en
  `docs/pendiente/fase1_pns_ai_17_3996.md` (decisiones 60 a 113): etapas F1.1 a F1.5 y hallazgos F1-1 a F1-12. Van al
  port como correcciones F1-2, F1-6 a F1-12 y el caso 24 (con el parche 18); su enlace con los parches, en la sección 8
  de ese documento. Laboratorio: `17 failed, 0 error(s) of 56 tests`: los 13 `[HYPOTHESIS]` de la clasificación (su
  sección 8) y los de F1-6, F1-2, T2b (F1-9 y F1-10) y T3 (F1-11), que pasan a verde con el port.

  Fase 2: tandas preparadas (24/11/2026) en `docs/pendiente/fase2_pns_ai_17_3996.md` (decisiones desde la 114): T0
  (tests de no regresión, registro de parches y regla de terceros) y T1 a T10, con los 21 parches y las correcciones
  de la fase 1, sin cambiar la versión de los manifiestos (F1-4 queda fuera, decisión 115). Sigue la tanda T0.

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

**Versiones (23/11/2026):**
- **17.0 del fabricante** (base de `17.0-pns-ai`): `pns_base` 17.0.1.2.92, `pns_ai_mcp` 17.0.3.1.996 y `pns_ai_chatboo`
  17.0.2.1.597.
- **14.0 del fabricante hoy** (vista en GitHub el 23/11/2026, sin descargar): `pns_base` 14.0.1.2.74, `pns_ai_mcp`
  14.0.3.1.996 y `pns_ai_chatboo` 14.0.2.1.597. Nuestra 14 y sus parches son de 3.1.973.
- **14.0.3.1.996:** no se descarga. No es destino ni lleva parches, y la clasificación de la fase 0 (23/11/2026) dejó
  cuatro parches en «cambiado», todos por el cambio de serie: esa copia no los aclararía.

## Plan

1. **Fase 0, viabilidad:**
   - comparar 17.0.3.1.996 con 3.1.973 (14) parche a parche: para cada parche vivo del índice de la 14, el código que
     tocaba en 3.1.973 frente al de la 17.0.3.1.996, clasificado en «igual» (se pasa tal cual), «cambiado» (decidir si
     el fabricante lo corrigió o hay que adaptar el parche), «desaparecido» o «no aplica»; de los retirados (10, 13, 14,
     23, 30 y 31), confirmar en la 17 la corrección del fabricante. Lo que adaptaba `4e1ebcc` ya lo trae la
     17.0.3.1.996. Punto de partida: comparación con 3.1.973, §8.2 (24 de 25 tocan código común; el 20 hay que
     rehacerlo en owl2; el 18 y el 24 dependen de `res_users` de la 17). Resultado en
     `docs/pendiente/clasificacion_parches_pns_ai_17_3996.md` de esta rama;
   - instalar los tres módulos en un laboratorio de la 17 (`odoo-dev 17 paridad` antes; librerías `openpyxl`,
     `reportlab` y `requests`), pasar los tests del fabricante y confirmar lo que la clasificación deja para el
     laboratorio (su sección 8).
2. **Fase 1:** analizar el código que solo se activa en la 15 o superior y que en la 14 no se revisó
   (`ir_ui_view_patch.py`, assets, rutas JSON, cliente de Chatboo), con el criterio de los PNS. Alcance y etapas:
   `docs/pendiente/fase1_pns_ai_17_3996.md`. Hecha el 24/11/2026; el enlace con la fase 2, en su sección 8.
3. **Fase 2:** portar y aplicar los parches en esta rama, con sus tests. Tandas y estado:
   `docs/pendiente/fase2_pns_ai_17_3996.md`.
4. **Fase 3:** staging en la 17, cliente y merge commit en `17.0`.

## Abierto

- **Una sola copia de trabajo:** el laboratorio de la 14 y el de la 17 montan `third_party` según la rama activa; hay
  que decidir cómo trabajar con los dos a la vez.
- **Manifiestos:** los del fabricante llevan el prefijo `17.0.`; los retirados no lo llevaban.

## Documentos de la 14 (rama `14.0`)

`docs/specs/comparacion_pns_ai_3-1-973.md` (§8.2), `docs/specs/analisis_pns_base.md` (§2.3),
`docs/pendiente/parches_pns_ai.md` («Índice de la rama 14.0-pns-ai-3973»), `docs/pendiente/pns_ai_decisiones.md` (N15).
