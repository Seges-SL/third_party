# Análisis: posible parche 5 (Gemini 3 por el protocolo OpenAI: `thought_signature`)

- **Rama:** `14.0-pns-ai-3`
- **Fecha:** 2026-10-15
- **Versión del fabricante analizada:** `pns_ai_mcp` 14.0.3.1.782 · `pns_ai_chatboo` 14.0.2.1.453
- **Estado:** **Aplicado (parche mínimo)** el 2026-10-16 (sección 3; ampliaciones opcionales no
  aplicadas) y **validado en staging (16/10/2026)** (ver «Plan de prueba»). Ver `parches_pns_ai.md`,
  «Parche 5», la revisión de N2 en `pns_ai_decisiones.md` y PNS-93 en `seguimiento_informe_pns_ai.md`.
- **Relacionado:** `docs/pendiente/parches_pns_ai.md` (parches 1-4), `plan_staging_pns_ai.md`.

## Problema

En staging, con Gemini 3.5, 3.6 y 3.7-flash configurados con `protocol = openai` y endpoint
`…/v1beta/openai/chat/completions`, todo turno de Chatboo en el que el modelo llama a una
herramienta (`relaxaicode`) falla en la **petición siguiente** del bucle de herramientas con:

```
HTTP 400 … Function call is missing a thought_signature in functionCall parts
```

«Test Connection» funciona porque no envía herramientas (`models/ai_provider.py:995-997`,
`tools=None`). En `pns_ai_mcp/lib/llm/` no aparecen `thought_signature` ni `extra_content`.

**Cómo reproducirlo:** proveedor Gemini 3.x con protocolo `openai` → Chatboo → cualquier
pregunta que obligue a consultar datos (p. ej. «¿cuántos clientes hay?»). La primera ronda
devuelve el `tool_call`; la segunda ronda (con el resultado de la herramienta) recibe el 400.

## 1. Qué dice la documentación de Google

Fuente principal: <https://ai.google.dev/gemini-api/docs/generate-content/thought-signatures>
(página «Thought signatures — Gemini Generate Content API (Legacy)»). Las URL indicadas en el
encargo ya no contienen este detalle (consultadas el 2026-10-15):

- <https://ai.google.dev/gemini-api/docs/thinking>: reescrita para la *Interactions API*; su
  sección «Thought signatures» solo cubre los modos *stateful/stateless* de esa API.
- <https://ai.google.dev/gemini-api/docs/openai>: solo dice que «Gemini 3 supports OpenAI
  compatibility for thought signatures in chat completion APIs» y enlaza a la página de firmas.
- <https://ai.google.dev/gemini-api/docs/thought-signatures>: redirige a la de *thinking*.

### Campo exacto

- **Respuesta no streaming (OpenAI compatibility):** cada elemento de
  `choices[0].message.tool_calls[]` lleva, junto a `id`, `type` y `function`, el campo
  hermano `extra_content`:
  ```json
  {"id": "…", "type": "function",
   "function": {"name": "relaxaicode", "arguments": "{…}"},
   "extra_content": {"google": {"thought_signature": "<base64 opaco>"}}}
  ```
- **Streaming:** la página de Google no da un ejemplo de streaming para OpenAI compatibility;
  su nota de FAQ 3 dice que hay que leer el stream completo hasta `finish_reason`. Un
  informe público de un cliente (cherry-studio #12729) muestra un `chat.completion.chunk`
  real en el que **la llamada llega completa en un único delta** (`id`, `function.name`,
  `function.arguments` y `extra_content` en el mismo objeto) y **sin el campo `index`** en
  el elemento de `delta.tool_calls[]`. Otro cliente (opencode PR #51768) añade un caso de
  prueba con `extra_content` que llega antes que la identidad de la llamada. Conclusión
  prudente: el parche debe recoger `extra_content` de **cualquier** delta del tool_call.
- **Llamadas paralelas:** solo el **primer** `functionCall` de cada paso lleva firma; los
  siguientes no. Orden obligatorio: FC1+firma, FC2, FR1, FR2 (intercalar FC/FR da 400).
- **Llamadas secuenciales** (varios pasos en el mismo turno): cada paso tiene su firma y hay
  que devolverlas **todas**.

### Cómo devolverla

Tal cual se recibió, en el mismo `tool_call` del mensaje `assistant` que se reenvía en el
historial (mismo `extra_content.google.thought_signature`). Es un valor opaco: no se
interpreta ni se modifica.

### Alcance de la obligación

- Validación **estricta solo en el turno en curso**: «Only current turn is required; we
  don't validate on previous turns».
- El turno en curso empieza en el **último mensaje `user` con contenido estándar (texto)**;
  todos los pasos de llamada a función posteriores forman parte de él.
- Regla: «The **first** `functionCall` part in **each step** of the current turn **must**
  include its `thought_signature`». Si falta → 400.
- En respuestas de texto (sin llamadas) la firma, si llega, es recomendable devolverla pero
  **no** se valida.
- Aplica estrictamente a Gemini 3 y 4. En Gemini 2.5 es opcional.

### Valor para llamadas no generadas por el modelo

Sí existe: para historial inyectado o migrado se puede poner como firma
`"context_engineering_is_the_way_to_go"` o `"skip_thought_signature_validator"`, que
desactivan la validación de esa llamada. Google desaconseja inyectar llamadas propias.

## 2. Recorrido del dato en el código

### Driver OpenAI (`pns_ai_mcp/lib/llm/drivers/openai_driver.py`)

- **No streaming** — `chat_completion` (`:221-232`) → `_openai_chat` (`:449-537`): devuelve
  `response.json()` **sin transformar** (`:537`). Si Gemini envía `extra_content`, llega
  intacto a quien llame. Pero **el bucle de herramientas de Chatboo no usa este camino**.
- **Streaming** — `iter_chat` (`:573-664`), el que usa el bucle de herramientas:
  - `:645-657`: por cada `delta.tool_calls[]` crea/actualiza una fila en `calls`, indexada
    por `tc.get('index', 0)`, con **solo** `id`, `type` y `function.{name, arguments}`.
    **Aquí se pierde `extra_content`**: es el origen del 400.
  - `:661-664`: el mensaje final es `{'role': 'assistant', 'content': text,
    'tool_calls': [calls[i] for i in sorted(calls)]}`, que se entrega en
    `{'done': True, 'message': …, 'usage': …}`. Ese es el formato interno (el mismo de
    OpenAI, sin campos extra).
- **Petición** (`:584-598`): `messages` pasa por `_with_images` → `_coalesce_system`
  (`:235-277`), que copia cada mensaje con `dict(m)` y **reenvía `tool_calls` tal cual**.
  Si el dict de la llamada llevara `extra_content`, saldría en la petición sin tocar nada más.

### Motor (`pns_ai_mcp/utils/agent_engine.py`)

- **Construcción inicial de `messages`** (`:2671-2838`): `system` + historial + mensajes
  auxiliares + mensaje del usuario. El historial pasa por `compact_history_for_llm`
  (`utils/history_compact.py:61-86`), que **descarta los mensajes `tool`, los `assistant`
  que solo tienen `tool_calls`, y reconstruye cada `assistant` como
  `{'role', 'content'}`** (sin `tool_calls`).
  → **Los tool_calls de turnos anteriores nunca se reenvían**; no hace falta firma para ellos
  (y Google no la valida fuera del turno en curso).
- **Bucle de herramientas** (`:3113` en adelante, `while round_n < MAX_ROUNDS`):
  - `:3149-3169`: crea el driver y llama a `driver.iter_chat(messages, tools=…)`.
  - `:3186-3196`: en el evento `done`, copia **los mismos dicts** del driver a
    `tool_calls_buffer[idx] = tc` (sin reconstruirlos).
  - `:3604-3608`: añade a `messages` (en memoria) el mensaje del asistente con
    `"tool_calls": list(tool_calls_buffer.values())` — de nuevo los mismos dicts.
  - `:3755-3758`: ejecuta cada llamada leyendo solo `function.name`, `function.arguments` e
    `id`.
  - `:4518-4523`: añade un mensaje `{"role": "tool", "tool_call_id", "name", "content"}` por
    llamada (orden FC1, FC2, FR1, FR2: correcto para Gemini).
  - Vuelve al inicio del bucle y envía la lista `messages` completa.
- **Entre pasos del mismo turno** la lista `messages` se mantiene **en memoria**; no se
  reconstruye desde BD. Por tanto, basta con que el driver conserve `extra_content` en el
  dict del tool_call para que viaje solo hasta la siguiente petición.
- Mensajes `user` insertados en mitad del turno (empujones de reintento `:3316`, `:3358`; el
  cierre de `:329-361` añade `CLOSING_AFTER_PROBE`): para Gemini abren un «turno en curso»
  nuevo, así que las llamadas anteriores dejan de validarse. No causan el error.
- Mensajes `system` insertados en mitad del bucle (`:3711`): `_coalesce_system` los funde en
  el primero, así que no rompen el orden FC/FR.
- **Fallback de llamadas en texto** (`:3215-3240`): si el modelo escribe el JSON de la
  llamada en el `content`, se construye un tool_call sin firma. Con Gemini esa llamada iría
  en la siguiente petición como `functionCall` del turno en curso sin firma → **400 también
  ahí**. Es un caso raro (Gemini emite llamadas nativas), no cubierto por el parche mínimo.
- **Failover entre proveedores** (`:2340-2400`): si el proveedor falla, el siguiente
  **reinicia el turno** (nuevo `messages`); si ya hubo efectos, no reintenta. Los tool_calls
  de Gemini nunca llegan a otro proveedor.
  Ojo: hoy el 400 de Gemini se convierte en `ProviderConnectionError` y dispara este
  failover; con un solo proveedor, el usuario ve el error.

### pns_ai_chatboo

No interviene en el dato: `chatboo_async_request.py:575-603` crea `AgentEngine` y le pasa el
historial de la sesión. Ninguna parte de `pns_ai_chatboo` lee ni escribe `tool_calls` (grep
sin resultados); el historial persistido son stubs de usuario/asistente
(`history_compact.append_turn_stub`).

### Registro de actividad (ai_log)

El bucle registra la petición con `log_provider_llm_request(… num_messages, num_tools …)`
(`agent_engine.py:3134-3146`, **sin** `prompt_data`) y la respuesta con los **nombres** de
las herramientas (`:3249-3260`). La firma no se registra. Solo el proxy no streaming
(`models/ai_execution_engine.py:39-49` → `:652` `prompt_data={'messages': messages}`)
guarda los mensajes, y ese camino no lleva herramientas en Chatboo.

## 3. Propuesta de parche mínimo (aplicado el 2026-10-16)

### Archivo y función

Un único cambio en `pns_ai_mcp/lib/llm/drivers/openai_driver.py`, función `iter_chat`,
dentro del bucle `for tc in delta.get('tool_calls') or []:` (tras `:656`):

```python
                    if fn.get('arguments'):
                        row['function']['arguments'] += fn['arguments']
                    # Seges: parche de compatibilidad (Gemini 3 por el protocolo OpenAI:
                    # thought_signature). Ver docs/pendiente/parches_pns_ai.md
                    # Gemini exige devolver extra_content.google.thought_signature en el
                    # tool_call; otros proveedores no lo envían y la fila no cambia.
                    extra = tc.get('extra_content')
                    if isinstance(extra, dict) and extra:
                        merged = dict(row.get('extra_content') or {})
                        merged.update(extra)
                        row['extra_content'] = merged
```

- **Unas 9 líneas añadidas** (4 de código, 3-4 de comentario), ninguna modificada.
- **Cómo conserva la firma:** la fila del tool_call guarda `extra_content` solo si el delta lo
  trae. El motor ya copia ese dict sin reconstruirlo (`agent_engine.py:3194-3195` y
  `:3604-3608`) y el driver lo reenvía tal cual (`_coalesce_system`). No hace falta tocar
  `agent_engine.py`, `history_compact.py` ni `pns_ai_chatboo`.
- **Otros proveedores OpenAI-compatibles:** no envían `extra_content` → la condición no se
  cumple → la fila y la petición siguiente son idénticas byte a byte a las actuales.
- **Python 3.7:** solo `dict`, `isinstance` y `update`; sin anotaciones nuevas ni sintaxis
  posterior a 3.6.
- **Camino no streaming:** no necesita cambio (`_openai_chat` devuelve el JSON crudo, que ya
  incluye `extra_content`).
- **Comentario:** prefijo `# Seges: parche de compatibilidad` como los parches 1-4, para que
  `grep -rn "Seges: parche de compatibilidad"` lo liste. El paréntesis cambia porque este no
  es un problema de Odoo 14, sino de compatibilidad con Gemini. Al aplicarlo, añadir la
  entrada «Parche 5» en `parches_pns_ai.md` con su comprobación:
  `grep -n "extra_content" pns_ai_mcp/lib/llm/drivers/openai_driver.py` (si el fabricante lo
  incorpora, este parche sobra).

### Ampliación opcional (no imprescindible para el error observado)

1. **Llamadas paralelas sin `index`.** Según el informe de cherry-studio, Gemini no envía
   `index` en `delta.tool_calls[]`. Con `idx = tc.get('index', 0)` (`:646`), dos llamadas
   paralelas que lleguen completas en deltas distintos caerían en la misma fila: el `id` se
   sobrescribe y `name`/`arguments` se **concatenan** (`relaxaicoderelaxaicode`, JSON roto).
   Es un fallo distinto del 400, pero en la misma zona. Corrección posible (~6 líneas): si el
   delta no trae `index` y trae un `id` distinto del de la última fila, abrir una fila nueva
   (`idx = len(calls)`). **Antes de aplicarla, confirmarlo en staging** con una pregunta que
   provoque dos llamadas en la misma ronda.
2. **Fallback de llamadas en texto** (`agent_engine.py:3215-3240`): poner
   `extra_content = {'google': {'thought_signature': 'skip_thought_signature_validator'}}` en
   las llamadas recuperadas **solo** si el endpoint es de Gemini. Requiere detectar el
   proveedor en el motor (más intrusivo). No recomendado mientras no se observe el caso.

### Recomendación

Aplicar solo el parche mínimo, probarlo en local con un test unitario del driver (stream
simulado con y sin `extra_content`) y en staging con Gemini 3.x. Decidir la ampliación 1 según
lo que se vea en staging con llamadas paralelas.

## 4. Riesgos

| Ámbito | Impacto | Motivo |
| --- | --- | --- |
| OpenAI, Azure OpenAI, Ollama, vLLM/OVH | Ninguno | No envían `extra_content`; la condición no se cumple y el mensaje es el mismo de hoy. |
| OpenRouter | Ninguno o positivo | Hereda `iter_chat` (`openrouter_driver.py`). Si OpenRouter reenviara `extra_content` de Gemini, ahora se conservaría; si no, igual que hoy. |
| Anthropic / SystemOne | Ninguno | Drivers propios; los tool_calls de Gemini nunca les llegan (el failover reinicia el turno y el historial previo no lleva `tool_calls`). |
| Proveedor que rechace campos desconocidos | Muy bajo | Solo recibiría `extra_content` si él mismo lo hubiera enviado en esa respuesta. |
| Tamaño de la petición | Bajo | Cada firma son unos cientos de bytes a pocos KB en base64, solo en el turno en curso. La estimación de tokens (`agent_engine.py:2494-2496`) la cuenta, así que el recorte de contexto sigue siendo coherente. |
| ai_log | Ninguno | El bucle registra contadores y nombres de herramientas, no los mensajes; la firma no se guarda en `ai.log`. |
| Historial de sesión | Ninguno | `compact_history_for_llm` y `append_turn_stub` no guardan `tool_calls`; la firma no se persiste ni se reenvía en turnos posteriores. |
| Seguridad (permisos, confirmaciones, sandbox) | Ninguno | El parche no toca `agent_engine.py`, `mcp_decorators`, `tool_visible_to`, la ejecución de herramientas ni las confirmaciones. Solo copia un valor opaco del proveedor al mismo proveedor. La lista de herramientas visibles (`get_tools_schema`) no cambia. |
| Gemini 2.5 | Ninguno | La firma es opcional; si llega, devolverla es lo recomendado. |
| Actualización del fabricante | Medio (mantenimiento) | Como los parches 1-4: desaparece al sustituir el código; hay que comprobarlo y volver a aplicarlo si sigue haciendo falta. |

## Plan de prueba (cuando se aplique)

1. **Local:** test del driver con un stream simulado: (a) tool_call con `extra_content` →
   el mensaje final lo conserva; (b) sin `extra_content` → mensaje idéntico al actual;
   (c) `extra_content` en un delta posterior al del `id`. `odoo-dev 14 tests pns_ai_mcp`.
2. **Staging (Gemini 3.5, 3.6 y 3.7-flash, protocolo openai):**
   - Pregunta con una sola llamada a `relaxaicode` → respuesta sin 400.
   - Pregunta que obligue a dos rondas de herramientas en el mismo turno (secuencial).
   - Pregunta que provoque dos llamadas en la misma ronda (paralelas): comprobar en el log
     del servidor si llegan con `index` (decide la ampliación 1).
   - Segundo turno en la misma conversación (el historial no debe reenviar tool_calls).
3. **No regresión:** el mismo turno con un proveedor OpenAI/Ollama ya configurado.
4. **ai_log:** las filas de petición/respuesta del turno muestran los mismos datos que antes.

**Resultado (16/10/2026):**
- **Local:** casos (a), (b) y (c) correctos con el driver en la imagen `odoo-dev:14` (ver
  `parches_pns_ai.md`, «Parche 5», comprobación 2).
- **Staging: validado.** Desplegado con el commit `27cadbb`. Con `gemini-3.6-flash`,
  `gemini-3.5-flash-lite` y `gemini-3.5-flash` (`3.7-flash` y `3.8-flash` daban 503 con frecuencia):
  turnos con varias rondas de herramientas y segundo turno en la misma conversación, sin 400.
- **Llamadas paralelas: no observadas.** La ampliación 1 sigue sin aplicar; se decidirá si aparecen.
- **No regresión con otro proveedor OpenAI-compatible:** no probada (en staging solo había Gemini).

## Fuentes

- Google, «Thought signatures» (Generate Content API, Legacy):
  <https://ai.google.dev/gemini-api/docs/generate-content/thought-signatures>
- Google, «Gemini thinking»: <https://ai.google.dev/gemini-api/docs/thinking>
- Google, «OpenAI compatibility»: <https://ai.google.dev/gemini-api/docs/openai>
- Ejemplo de chunk de streaming real: <https://github.com/CherryHQ/cherry-studio/issues/12729>
- Firma que llega antes que la identidad de la llamada: <https://github.com/anomalyco/opencode/pull/51768>
- Forma no streaming en `tool_calls`: <https://github.com/pydantic/pydantic-ai/issues/9947>
