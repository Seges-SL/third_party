---
skill: forecast
name: Weather forecast
description: Daily weather for one or more places from Open-Meteo, a site on the URL whitelist; the company city and the next 7 days by default.
agent_codes: pns_ai_chatboo
version: 5.0
param_schema: {"place": {"type": "string", "desc": "One or more places separated by commas, as the user wrote them. A country in brackets picks among homonyms. null for the company city."}, "start": {"type": "string", "desc": "First day as YYYY-MM-DD. null for today."}, "days": {"type": "integer", "desc": "How many days from the first day, 1 to 16.", "default": 7}}
arg_hint: place=Paris, Rome days=3
args_policy: default
sequence: 60
active: true
context_codes:
---
[FORECAST]
Use with /forecast, or when the user asks for the weather somewhere.

WHAT IT SHOWS
One table per place: sky, temperatures, rain, wind, UV, sunrise and sunset.
The data comes from Open-Meteo through fetch_url steps that the URL
whitelist lets run without a confirmation. The code runs three rounds:
geocode, forecast, table. With no place it uses the city of the current
company, with its state (or country) to pick among homonyms.

HOW TO PRESENT THE RESULT
- The code already returns the table. Do not invent places or figures.
