---
skill: users
name: Users
description: System users (archived included) with type, last login and live presence; online=true lists only who is connected now. Each row opens the user.
agent_codes:
version: 1.0
required_groups: pns_ai_mcp.group_ai_admin
param_schema: {"online": {"type": "boolean", "desc": "true to list only the users connected right now. null for every user."}}
arg_hint: online=true
args_policy: default
sequence: 20
active: true
context_codes:
---
[USERS]
Use with /users, or when the user asks who uses the system or who is
connected now.

WHAT IT SHOWS
A table built by the code. The name of each user links to the user form.
Presence is empty for users who are not connected.

HOW TO PRESENT THE RESULT
- Show the table as the code returns it. Do not invent users or presence.
