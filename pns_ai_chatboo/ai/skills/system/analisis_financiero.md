---
skill: analisis-financiero
name: Financial analysis
description: Narrative financial situation report (JYDY-14): KPIs, liquidity, debts, collections, ratios, facilities; configurable period.
agent_codes: pns_ai_chatboo
version: 2.14
painter: painter-free
param_schema: {"periodo": {"type": "string", "desc": "Canonical period ONLY: null/empty, ytd, integer 1-60 (= last N months), YYYY, YYYY-YYYY, or YYYY-MM. Convert NL like 'últimos dos años'/'last 2 years' → '24'. Never return prose."}}
arg_hint: ytd | 12 | 2025 | 2024-2025 | 2025-03 | ?
args_policy: default
sequence: 43
active: true
context_codes:
---
[ANALISIS-FINANCIERO]
Úsalo con /analisis-financiero (gemelo EN: /financial-health).

CIFRAS / TABLAS = code_body (deterministas; el motor las pinta en HTML).
NARRATIVA = tú (LLM) con esqueleto FIJO — sin tablas Markdown.
Params: deterministic first; `param_schema` enables ONE AI extract only
when free text does not resolve the period (NL → canonical token).
`?` / help / ayuda / options → the engine already painted the help card; do not rewrite.
El JSON trae `report_outline` + `closing_required`: respétalos al pie de la letra.

ÁMBITO TEMPORAL ÚNICO: el periodo del JSON (`PERIOD` / label / títulos) rige TODAS
las tablas y la narrativa. NO digas «YTD» salvo que el label sea realmente YTD.

TÍTULO: la PRIMERA línea del informe es UN solo H1 (`# …`) redactado por ti
a partir del periodo (no copies `PERIOD=` ni el summary técnico). Ejemplos de
forma (adapta N / año / rango): `# Análisis financiero de los últimos 12 meses`;
`# Análisis financiero del YTD 2026`; `# Análisis financiero del año 2025`;
`# Análisis financiero del periodo 2024–2025`.
Justo DEBAJO del H1, si el JSON trae `company`, escribe ese nombre TAL CUAL
(viene de la empresa activa de Odoo; no lo traduzcas ni añadas etiqueta
«Empresa»/«Company»).

ARGS (fijos; copiar literal tras el slash)
- vacío → últimos **12 meses** (default)
- ytd · N (1–60) · YYYY · YYYY-YYYY · YYYY-MM
- texto libre (p. ej. «últimos dos años») → IA → token canónico
- ? | ayuda | help | options → ayuda HTML (sin IA, nunca)

ESQUELETO FIJO (después del H1; copiar estos títulos SIEMPRE, en este orden; = `report_outline`):
## Análisis
### Fortalezas
### Debilidades y riesgos
### Liquidez y deudas
### Pólizas
## Conclusión
## Recomendaciones

En **Recomendaciones** (SIEMPRE la última sección, nunca la omitas):
- 2–4 bullets de acciones concretas con cifras.
- Cierra con exactamente: `Línea recomendada de actuación: …`
  (si no hay urgencia: `Línea recomendada de actuación: sin acción urgente; mantener vigilancia.`).
Empieza por lo material (qué cambió, qué aprieta, qué hacer).
No inventaries cada tabla del JSON ni cada partida; las tablas HTML ya
muestran las cifras. Cita un número solo si sostiene el juicio.
Si un apartado del esqueleto no aporta, una frase corta basta.
Sin tablas pipe (ya van en HTML). Sin botones Gráfico.
