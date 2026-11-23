# Changelog

What changes for people who use this module, one section per published version, newest first. The heading is the git tag.

## owl1-3.1.996_owl2-3.1.996_owl3-3.1.996 (2026-11-19)

- Spanish: settings help, import and export wizards, errors and selections are translated, and Odoo 16 now loads the Spanish catalogue. The activity log stays in English on purpose.
- AI lists: each column takes the width of its content and can be hidden; Odoo 15 and 16 no longer cut the name.
- Importing users: an Odoo user missing from this database is a warning with its login, not a bare detail line.

## owl1-3.1.988_owl2-3.1.988_owl3-3.1.988 (2026-11-16)

- When the person behind a plan cannot read a record, the change journal notes it as a warning instead of an error. The plan behaves as before.

## owl1-3.1.987_owl2-3.1.987_owl3-3.1.987 (2026-11-15)

- Provider roles: "Fallback" is now "Fallback role", and its help says it is another role, not another provider. The next provider with the same role on the agent's list always answers when the first fails.
- The role list shows the "Use the fallback role" tick only on roles that have one.

## owl1-3.1.986_owl2-3.1.986_owl3-3.1.986 (2026-11-15)

- New provider role "Embedding" (a text into a vector), ready for a module that searches documents by meaning. The engine does not use it itself.
- README: a new section explains the three MCP tools and why three instead of one tool per task.

## owl1-3.1.985_owl2-3.1.985_owl3-3.1.985 (2026-11-12)

- Odoo 17: list views open again; the safe-plan buttons asked for the bus in a way Odoo 17 rejects ("methods is not iterable").
- Odoo 16: the engine's field widgets load again; their screen templates were missing there.
- Odoo 14: an AI log entry no longer drops the caller's unsaved changes, so the entry is always written.
- Apps page and README: each Odoo version links to its page on www.patanegra.com.

## owl1-3.1.981_owl2-3.1.981_owl3-3.1.981 (2026-11-10)

Store listing only; the module code is the one of owl1-3.1.980_owl2-3.1.980_owl3-3.1.980.

- The module is now named "PNS AI Engine — MCP": the store grid cut "MCP Server" in four columns; "server" stays in the summary, which the store search also reads.

## owl1-3.1.980_owl2-3.1.980_owl3-3.1.980 (2026-11-10)

Store listing only; the module code is the one of 3.1.979.

- The module is now named "PNS AI Engine — MCP Server", so the Odoo Apps card says what it is next to the other MCP servers.
- New Odoo Apps cover: icon, headline and one line of facts (free, Apache 2.0, Odoo Community 14.0 to 20.0). The previous cover carried a paragraph and the series chips, unreadable at the size of the store grid.

## owl1-3.1.979_owl2-3.1.979_owl3-3.1.979 (2026-11-10)

- A skill's result can be worked on in the next turn. After `/sales` (or any skill drawn on the server), "now for 2025" or "make a report with this data" used to find nothing: the skill left neither its rows nor its code in the session, and the chat even dropped the dataset of the turn before. The skill now leaves both, like any query does, with the same size cap. Works for the painted table and for the report mode.

## owl1-3.1.978_owl2-3.1.978_owl3-3.1.978 (2026-11-09)

- A secret column no longer ends the turn. When the model's code touched a credential column by accident (for example by looping over every field of a task, which includes its portal `access_token`), the guard's refusal was treated like a permission denial and the chat stopped with that message. It now goes back to the model as a code fix with a hint (name the columns, leave that one out) and the code runs again. The value is still never read; real permission denials still stop the turn.

## owl1-3.1.977_owl2-3.1.977_owl3-3.1.977 (2026-11-09)

- Odoo 19 and 20 install and update again. The record rule of 3.1.975 (`shared_user_ids`) crashed on those series with `Invalid domain: can't adapt type 'OrderedSet'`: the newer domain engine hands the user ids as a set, and the search only expected a list. Any iterable works now.

## owl1-3.1.976_owl2-3.1.976_owl3-3.1.976 (2026-11-09)

- Odoo 14 installs and updates again. The Spanish catalog of 3.1.975 had four entries without the module comment Odoo 14 demands when it loads translations, so the registry failed to load (`translate.py ... 'NoneType' object has no attribute 'groups'`). Fixed catalog, owl1, owl2 and owl3. The *Required groups* label of trusted actions is back; the skill and context field is *Shared with groups*.

## owl1-3.1.975_owl2-3.1.975_owl3-3.1.975 (2026-11-09)

- Skills and contexts can be shared with groups. The owner ticks the groups on the form (*Shared with groups*): members see and use it; the owner keeps editing it. With no owner and no groups, everyone with access to the agent uses it. Contexts get the field now; on skills it existed as *Required groups* and only ruled the slash menu, so a skill shared with a group was still hidden from its members in the list. One rule now, on the record rule, the search and the prompt: owner, member, or open.
- A context shared with a group goes into the prompt of its members only, not into the agent's shared cache.

## owl1-3.1.974_owl2-3.1.974_owl3-3.1.974 (2026-11-09)

- An AI administrator can change the owner of a skill, or clear it. The form showed the field locked for everyone; the model already allowed it. Cleared: everyone with access to the agent sees and runs the skill. Another user: only that user. Writers still cannot touch the owner.

## owl1-3.1.973_owl2-3.1.973_owl3-3.1.973 (2026-11-09)

- Banners (Apps store, README and site) show the seven supported series, 14.0 to 20.0; the old ones still said 14 and 19. Images only.

## owl1-3.1.972_owl2-3.1.972_owl3-3.1.972 (2026-11-09)

- A confirmation card painted in the chat keeps its token while a badge counts the pending cards or the list is read again, so Confirm no longer fails with an old token. "Process this PDF" with a PDF attached works on the attachment instead of offering a download, on Odoo 20 too.
- Vendor bills from a document work outside Europe: several taxes on the same base (GST + PST, CGST + SGST, state + county sales tax) go on one line or as a group tax, a printed withholding is kept as a negative purchase tax, a document in another currency keeps its currency and its figures, and a bill without the issuer's tax id is matched by name without a warning. When none of your taxes reproduces the printed figures, the line goes without tax and the engine names the missing one.
- A till receipt dropped in the chat becomes a draft vendor bill too (the base worked out from the printed rate, or a question when none is printed). A card terminal slip is never booked: the engine looks for the bill of that merchant with that amount around that date and says whether it is booked and paid.
- The words that open a knowledge pack are capped per list (generic and per language), so a long generic list no longer silently drops the words of your language.
- Drop a supplier's bill (PDF, spreadsheet, photo or scan) in a chat that uses this engine and ask for it: the plan finds the vendor by tax id or name (or creates the contact as its first step), proposes the draft bill with one line per tax rate and the expense account from that vendor's history, and names any duplicate before proposing anything. Nothing is posted.
- Tested and published on every series from Odoo 14.0 to 20.0, one flat branch each. Odoo 20 has its own screen stack (Owl 3).
- Several companies: the AI reads and writes in the companies ticked in the company switcher (the active one first) or, with no screen, in the user's default company. An approved plan runs in the companies it was asked in, even if it is approved from another one.
- AI Administrator now includes AI Conversational, but an AI Administrator who is not a Settings administrator can no longer set a Settings administrator's API key (by generating it, pasting it or importing it). The users' AI permissions travel in the export and import; the import says when it left a key out. The Roles list has Tools to export and import the roles and which providers hold each one.
- A skill waiting for its arguments lets go when the next message is a different question, and a skill can propose a record as a form card that the person opens and saves.

## owl1-3.1.933_owl2-3.1.933 (2026-11-07)

- The Apps subtitle says what people search for: open source, Odoo Community 14 and 19, and the models it talks to (OpenAI, Claude, Ollama or any compatible one).

## owl1-3.1.932_owl2-3.1.932 (2026-11-06)

- A skill that calls an external API over several rounds finds its earlier calls again. Since 3.1.921 its code reads from a cursor of its own, which did not see the cached responses of the same turn; it asked for them again until the rounds ran out. The cache row is now committed as soon as it is written.

## owl1-3.1.931_owl2-3.1.931 (2026-11-06)

- The AI-generated mark also goes on HTML and Word exports, and on Excel files written when openpyxl is not installed. Text and Markdown have no properties and stay unmarked.

## owl1-3.1.930_owl2-3.1.930 (2026-11-06)

- Shorter pain line in the README and the description page: "AI for your clients as just another module. Open source, no licences."

## owl1-3.1.929_owl2-3.1.929 (2026-11-06)

- New headline: "AI inside your Odoo, for consultants." in the README, the description page and the banners.
- Excel and PDF files the engine writes carry a machine-readable mark that an AI system made them (EU AI Act, article 50): creator "PNS AI Engine" and the keyword "ai-generated" in the document properties. The content does not change. This covers Chatboo's Excel export too.

## owl1-3.1.928_owl2-3.1.928 (2026-11-06)

- README: new "Agents, roles and chains" section (English and Spanish). It explains the two agent types, the agents the module ships, the seven provider roles and their fallback, and how the provider chain is ordered and failed over.

## owl1-3.1.927_owl2-3.1.927 (2026-11-06)

- The module's website link now points to the public product page instead of the local description page. The description is still shown inside Odoo.
- README: the language line also links to the product page.

## owl1-3.1.926_owl2-3.1.926 (2026-11-05)

- README: new "What it does not do" and "Questions" sections, in English and Spanish, covering supported protocols, the MCP routes and the three MCP tools.

## owl1-3.1.925_owl2-3.1.925 (2026-11-05)

- App store description: the EN tab is now shown as selected, so the language switch reads as a switch.

## owl1-3.1.924_owl2-3.1.924 (2026-11-05)

- Security: sandboxed code can no longer reach the database connection or cursor, whether through the environment, error objects, string formatting or pattern matching. Only a short list of environment attributes is available.
- Security: skill code now runs in the read-only box (its own read-only cursor, secret columns closed), not on the caller's cursor.
- Fixed: simple results such as the current user's name failed to display after the sandbox hardening; they display again.
- App store description: the ES tab now jumps to the Spanish text and the tab bar stays fixed at the top.

## owl1-3.1.919_owl2-3.1.919 (2026-11-04)

- Store category changed to "Extra Tools", so the module can be found when browsing categories.
- New store summary: "Native AI engine and MCP server for Odoo: open LLM providers, a read-only sandbox, human-approved writes and agents as Odoo modules."
- New store thumbnail that shows the whole banner instead of a cropped one.

## owl1-3.1.917_owl2-3.1.917 (2026-11-04)

- Configuration backups and partial bundles now say what they are (`what`) and no longer write a schema version. Older files that carry one still import.

## owl1-3.1.916_owl2-3.1.916 (2026-11-04)

- Added ready-made provider examples (OpenRouter, OVH, OpenAI, Anthropic, Lemonade), without keys. Load them with Settings → AI Engine → Import configuration.
- README setup: install Chatboo if you want the chat (it brings the engine), and how to load a provider example.

## owl1-3.1.915_owl2-3.1.915 (2026-11-03)

- The module is now called "PNS AI Engine" in Apps and in the store. The menu inside Odoo is still "AI Engine".
- Refreshed banners, description page and README titles.

## owl1-3.1.914_owl2-3.1.914 (2026-11-03)

- README: Spanish banner, and an example `mcp.json` for connecting Cursor or another MCP client.
- README and description: Odoo 15.0 to 18.0 have no branch and are not tested. They can be built from `main` and should be tried on a test database first.

## owl1-3.1.913_owl2-3.1.913 (2026-11-03)

- Fixed: when capturing a skill, the usage example written by the user is kept as long as the keys it names are still in the schema. Before, it was always replaced by a generated one.
- Tests no longer depend on demo data, do not call the network on Odoo 14, and no longer commit in a separate cursor while a test runs.

## owl1-3.1.912_owl2-3.1.912 (2026-11-02)

- Maintenance release; no change in behaviour.

## owl1-3.1.911_owl2-3.1.911 (2026-11-02)

- Maintenance release; no change in behaviour.

## owl1-3.1.910_owl2-3.1.910 (2026-11-02)

- Maintenance release; no change in behaviour.

## owl1-3.1.909_owl2-3.1.909 (2026-11-02)

- README: full English and full Spanish versions, with "English · Español" links at the top.

## owl1-3.1.908_owl2-3.1.908 (2026-11-02)

- README: the banner image no longer shows broken.
- Setup reduced to four steps: install, become AI administrator, get the API key, add a provider.

## owl1-3.1.906_owl2-3.1.906 (2026-11-02)

- README now opens with the same content as the description page: banner, features and setup.

## owl1-3.1.905_owl2-3.1.905 (2026-11-02)

- First public release.
- Security: system actions are no longer callable over RPC; supervised plans run as the user who asked; per-user records are private; external server secrets are visible only to the AI administrator and left out of exports.
- Security: URL fetches block internal networks even after DNS changes; the sandbox cannot send mail or run actions; `/mcp` gives no details to unauthenticated callers and rejects other users' sessions.
- Fixed: skills that require a group were not imported. Voice: the provider form warns when an audio role is handled as chat.
