---
skill: sys-info
name: System information
description: Odoo version, series, database, server time, current user and company, user/company/module counts, and base URL.
agent_codes:
version: 1.4
args_policy: none
sequence: 20
active: true
context_codes:
---
[SYS-INFO]
Úsalo cuando el usuario pida información del sistema, versión de Odoo, estado del
servidor, hora del servidor o un resumen del entorno.

QUÉ HACE
Ejecuta el código del skill y devuelve una tabla Propiedad/Valor con los datos del
sistema (solo lectura).

CÓMO PRESENTAR EL RESULTADO
- Muestra la tabla tal cual la devuelve el código.
- Opcional: 1-2 frases de resumen (versión y usuario/compañía actuales).
- No inventes valores que no estén en la tabla.
