# i18n — `pns_ai_mcp` (owl2)

Spec canal: `pns_suite/docs/obsidian/roadmap/transversales/Transversal_Capacidades_Core.md` § i18n

## Catálogos en este módulo

| Archivo | Idioma | Estado |
| :--- | :--- | :--- |
| `es.po` | Español | ✅ Activo |
| `ar_001.po` | Árabe (RTL) | 🔜 Post-lanzamiento |

**Inglés** es la base (msgid fuente en XML/Python). No requiere `.po` propio.

**Regla de lanzamiento:** cada cadena nueva de UI (`_()`, `string`/`help` de campos, `t-translation` en JS, textos de vistas) → **actualizar `es.po` en el mismo commit**.

**RTL preparado:** el CSS RTL (`mcp_rtl.css`) y los tools de i18n (`i18n_debt_map.py`, `i18n_lint.py`) ya están listos. Cuando se active árabe, basta con completar `ar_001.po` — la infraestructura RTL no necesita cambios.

Código y msgid en **inglés**. Sin español/árabe hardcodeado en Python, XML ni JS.

Portugués (`pt_PT` / `pt_BR`) entra en capa 1 del canal cuando el módulo lo adopte.
