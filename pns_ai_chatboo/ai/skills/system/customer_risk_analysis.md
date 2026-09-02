---
skill: customer-risk-analysis
name: Customer risk analysis
description: Customer collection-risk score from six criteria: payment ratio, DSO, temporal spread, monetary volume, recency and due-date compliance.
agent_codes:
version: 1.5
param_schema: {"meses": {"type": "integer", "desc": "Calendar months to look back (default 24). null if the user does not specify."}, "min_deuda": {"type": "number", "desc": "Minimum outstanding debt in euros to include a customer (default 0). null if not specified."}, "top": {"type": "integer", "desc": "Maximum customers to show, highest debt first (default 30). null if not specified."}}
arg_hint: meses=24 min_deuda=0 top=30
args_policy: default
sequence: 10
active: true
context_codes:
---
[CUSTOMER-RISK-ANALYSIS]
Úsalo cuando el usuario pida análisis de riesgo de clientes, fiabilidad de cobro,
scoring de clientes, morosos o clasificación de clientes por pago.

QUÉ HACE
Calcula un score de fiabilidad de 0 a 100 por cliente (ejecutando el código del skill)
y devuelve una tabla ya ordenada y etiquetada por nivel de riesgo.

PARÁMETROS (híbrido; el código los lee del sandbox)
El texto del slash se parsea primero de forma determinista (`parse_skill_arguments` +
enrich de fechas). `param_schema` habilita un LLM ligero solo si quedan claves sin resolver.
- meses: período de análisis en meses naturales (default 24).
- min_deuda: umbral mínimo de deuda pendiente en € (default 0).
- top: límite de clientes, los de mayor deuda (default 30).

CÓMO PRESENTAR EL RESULTADO
- Muestra la tabla tal cual la devuelve el código (respeta los colores de fila y de score).
- Resume en 2-3 frases lo relevante: clientes bloqueados/problemáticos y dónde se
  concentra la deuda.
- Si no hay resultados, dilo con claridad; no inventes clientes ni cifras.

METODOLOGÍA (informativa; la autoridad es el código)
Score 0-100 que pondera 6 criterios: ratio de pago, DSO, dispersión temporal de pagos,
volumen pagado, recency y cumplimiento de vencimiento. Etiquetas: Premium / Fiable /
Con Riesgo / Problemático / Bloqueado.
