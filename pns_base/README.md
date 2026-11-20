# pns_base — Patanegra Soft Suite base layer

> **PATANEGRA Soft** (https://patanegra.com). Part of **Patanegra Soft Suite**.
> Apache License 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

Shared foundation for every `pns_*` module. Install this first. The others
list `pns_base` in `depends`. This module never depends on them.

Apps sheet: `static/description/index.html`.

| Path | Contents |
| :--- | :--- |
| `stacks/owl1/pns_base/` | Odoo 14 and 15 |
| `stacks/owl2/pns_base/` | Odoo 16 to 19 |
| `stacks/owl3/pns_base/` | Odoo 20 and later |

Every stack ships the same Python. The running version is read at runtime
(`ODOO_VERSION`). `owl1` / `owl2` / `owl3` exist for the JavaScript of sibling
modules and so the installer always copies the same layout.

## What it does

1. **Old-style screens on Odoo 17+.** XML is written the same in owl1 and
   owl2 (`attrs`, `<tree>`). On 17+ this module translates it on load
   (`models/ir_ui_view_patch.py`). Stacks do not do that: they are the web
   kit (OWL 1, OWL 2, Owl 3). If `attrs` cannot be translated, it is left and
   an ERROR is written (fail visible). Only `pns_*` views are touched.
2. **One name for jobs Odoo renamed** (`utils/compat.py`): same action,
   another signature per version (JSON route, user groups, cache).
3. **A small library:** toasts and reports (`utils/ui_feedback.py`),
   portable import/export (`portable_io`,
   `settings_io`), PDF and picture files on bytes (`pdf_io`: text, or page
   pictures for whatever vision model the caller uses; any picture stood
   up, shrunk, turned or made a PDF page), a full-screen
   picture viewer, the operation-result wizard, and the Apps sheet that
   embeds each module's `index.html`.

## How another module uses it

```python
# __manifest__.py
'depends': ['base', ..., 'pns_base'],
```

```python
from odoo.addons.pns_base.utils.compat import ODOO_VERSION, USER_GROUPS_FIELD
from odoo.addons.pns_base.utils import ui_feedback as pns_ui
```

## Odoo versions

| Series | Status |
| :--- | :--- |
| 14.0 – 20.0 | Tested. Flat branch published. |
| 13.0 and older | Not supported. |

Patanegra Soft Suite starts where its AI can run. Odoo 13 has no OWL, which the AI chat is built on. Odoo 8 to 10 run on Python 2, and Odoo 11 and 12 on Python 3.5; the AI engine needs Python 3.7. The suite keeps three stacks (`owl1` for 14.0 and 15.0, `owl2` for 16.0 to 19.0, `owl3` for 20.0 and later) and none for older series.

## Tests

| Where you are | What runs |
| :--- | :--- |
| `main` (multi-version tree) | `python -m pytest unit_tests`, with no Odoo. |
| A flat branch (`14.0` … `20.0`) | The Odoo test in `tests/`: the web client starts with Base's JavaScript and no error. It needs Chrome; without it Odoo skips it. The unit tests live on `main`. |

## License, marks, training

Apache-2.0. PATANEGRA Soft™, PATANEGRA Soft Suite™ and Chatboo™ are
trademarks of PATANEGRA Soft SL; this license does not grant them.

TDM / AI training is allowed (TDMRep `tdm-reservation = 0`). See NOTICE.

## Security

See [SECURITY.md](SECURITY.md). Bugs, ideas and questions: [CONTRIBUTING.md](CONTRIBUTING.md).
