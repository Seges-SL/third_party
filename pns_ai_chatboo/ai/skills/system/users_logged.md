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
Use when the user asks who is connected, logged-in users, users online or
recent user activity.

WHAT IT DOES
Runs the skill code and returns a table of connected users (status and last
signal). If presence data is missing, it returns the latest logins by date.

HOW TO PRESENT THE RESULT
- Show the table exactly as the code returns it.
- State how many users there are; if Status says "last login", clarify these
  are recent logins, not live presence.
- Do not invent users or statuses.
