---
skill: users-all
name: All users
description: All system users (including archived) with login, name, email, type (internal/portal), active flag and last access.
agent_codes:
version: 1.3
args_policy: none
sequence: 22
active: true
context_codes:
---
[USERS-ALL]
Úsalo cuando el usuario pida la lista de usuarios, todos los usuarios del sistema,
el censo de usuarios o un inventario de cuentas.

QUÉ HACE
Ejecuta el código del skill y devuelve una tabla con todos los usuarios (incluye
archivados), ordenada por login.

CÓMO PRESENTAR EL RESULTADO
- Muestra la tabla tal cual la devuelve el código.
- Puedes resumir el total y cuántos están activos vs. archivados.
- No inventes usuarios ni datos.
