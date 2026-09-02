---
skill: users-logged
name: Logged-in users
description: Users currently connected (bus online/away). If the bus is unavailable, last logins by date.
agent_codes:
version: 1.4
args_policy: none
sequence: 21
active: true
context_codes:
---
[USERS-LOGGED]
Úsalo cuando el usuario pida quién está conectado, usuarios logueados, usuarios en
línea o actividad reciente de usuarios.

QUÉ HACE
Ejecuta el código del skill y devuelve una tabla con los usuarios conectados (estado
y última señal). Si no hay datos de presencia, devuelve los últimos accesos por fecha
de login.

CÓMO PRESENTAR EL RESULTADO
- Muestra la tabla tal cual la devuelve el código.
- Indica cuántos usuarios hay; si la columna Estado dice "último acceso", aclara que
  son los accesos más recientes, no presencia en tiempo real.
- No inventes usuarios ni estados.
