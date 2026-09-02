---
skill: forecast
name: Weather forecast
description: Company-city forecast for the next 7 days by default; optional other cities; sky column uses weather emojis.
agent_codes: pns_ai_chatboo
version: 4.4
param_schema: {"lugar": {"type": "string", "desc": "City or cities (comma / and). Empty = company city (or state). Never invent a city.", "default": "company city"}, "fecha": {"type": "string", "desc": "today, tomorrow, next N days, or ISO YYYY-MM-DD. Empty = next 7 days.", "default": "7 days"}}
arg_hint: company city · 7 days
args_policy: default
sequence: 40
active: true
context_codes:
---
[FORECAST]
Use when the user asks for the weather, forecast, climate or temperature for a
place and/or date (/forecast).

PARAMETERS (sandbox; may be None)
Empty slash runs with defaults (args_policy=default). Deterministic parse first.
- Empty slash: company city (or state) and the next 7 days. Never invent a
  city. If the company has no city, the skill asks for a place.
- lugar / arguments: one or more cities separated by comma and/or «and»/«y»/«e»,
  optionally with a date. Any city: the skill geocodes via Open-Meteo.
- fecha: optional date text. If None / empty / null / default, next 7 days.
- Sky column: emoji + weather label for each day.

Do NOT use dir()/locals()/globals()/vars() to probe parameters — they always exist.

FLOW (automatic — skill resolves without the LLM)
Self-contained multi-round: the engine runs `propose_steps` (auto-confirmable
fetch_url) and returns bodies in `previous_result` until the table is ready:
1. Round 1: geocode each city (geocoding-api.open-meteo.com).
2. Round 2: one forecast per city (api.open-meteo.com/v1/forecast) with real
   lat/lon and `&city=<name>` embedded.
3. Round 3: parse and present (data/groups + footer).

LLM FALLBACK (rare)
- Geocode each city with fetch_url to
  `https://geocoding-api.open-meteo.com/v1/search?name=<city>&count=1&language=en`
- ONE propose_safe_operations with one forecast fetch_url per city (always
  include `city=<name>`).

FORBIDDEN
- One propose per city: batch fetches in a single proposal.
- Omitting `city=<name>` on forecast URLs.
- `import requests`/`urllib`: HTTP only via fetch_url.
- Inventing figures or card HTML.

Source: Open-Meteo.
