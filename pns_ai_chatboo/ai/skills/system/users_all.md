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
Use when the user asks for the user list, every system user, a user census or
an account inventory.

WHAT IT DOES
Runs the skill code and returns a table of every user (including archived),
sorted by login.

HOW TO PRESENT THE RESULT
- Show the table exactly as the code returns it.
- You may summarise the total and how many are active vs archived.
- Do not invent users or fields.
