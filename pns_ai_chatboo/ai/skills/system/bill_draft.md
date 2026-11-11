---
skill: bill-draft
name: Bill draft
description: For a vendor already in Contacts. Reads a supplier bill attached to the chat (PDF, spreadsheet, or a scan or photo such as jpg, png or webp), finds the vendor by its tax id among the existing contacts, the date and the largest amount, flags possible duplicates, and opens the vendor bill form with the vendor and the date filled in; lines, taxes and the reference are left to the person. A vendor that is not in Contacts yet, or the lines filled in, is the chat's job, not this skill's (drop the bill and ask). Nothing is saved until the person presses Save. A scan or a photo is read by an AI provider with the Vision role, which uses tokens.
agent_codes: pns_ai_chatboo
version: 1.0
param_schema: {"document": {"type": "string", "desc": "Name (or part of it) of the attached file to read. null for the newest attachment."}}
arg_hint: attach the bill; optional file name
args_policy: default
sequence: 54
active: true
context_codes:
---
[BILL-DRAFT]
Use when the user attaches a supplier bill or receipt and wants it entered,
or asks whether an attached bill is already booked (/bill-draft).

WHAT IT DOES
Reads the newest attachment of the conversation (or the one named) and
returns a card. The card lists what was found and opens the vendor bill form
with the vendor and the bill date filled in. Lines, taxes and the bill
reference are left to the person. Closing the form discards it; only Save
writes, with the person's own rights.

COST
A PDF with text and a spreadsheet are read for free. A scanned PDF or a
photo (jpg, png, webp, …) has no text: when it is attached, Chatboo sends its
pages to an AI provider with the Vision role to transcribe them, once. That
call uses tokens and is billed by that provider. The skill itself makes no AI
call. With no Vision provider the scan cannot be read and the skill says so.

PARAMETERS (sandbox; may be None)
- document: name or part of the name of the attached file.

LIMITS (say them when they bite)
- Only vendors already in Contacts, matched by the tax id printed on the
  document. When the card says the vendor was not found, tell the person
  that dropping the bill and asking to register it proposes the vendor and
  the bill with its lines (business documents knowledge), and that this skill
  does not.
- Lines, taxes and the reference are never filled in by this skill.

HOW TO PRESENT THE RESULT
- The card is the answer. Do not repeat it in prose.
- Never claim the bill was created or booked: it is not, until the person
  saves it.

METHODOLOGY (informative; the code is authoritative)
- Vendor: a contact whose tax id appears in the document text (with or
  without the country prefix), not one of the user's own companies.
  Suppliers first.
- Date: the first date in the document, read in the order of the user's
  language (day/month or month/day).
- Amount: the largest amount with two decimals, either decimal mark. It is
  shown to be checked, not filled in.
- Possible duplicates: bills or refunds of that vendor, not cancelled, with
  the same total and, when the date was found, the same bill date (a
  monthly bill of the same amount is not a duplicate).
