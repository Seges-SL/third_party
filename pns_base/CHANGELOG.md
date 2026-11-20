# Changelog

What changes for people who use this module, one section per published version, newest first. The heading is the git tag.

## owl1-1.2.69_owl2-1.2.83_owl3-1.2.83 (2026-11-09)

- Banners (Apps store, README and site) show the seven supported series, 14.0 to 20.0; the old ones still said 14 and 19. Images only.

## owl1-1.2.68_owl2-1.2.82_owl3-1.2.82 (2026-11-09)

- Seven tested series, each with its flat branch: 14.0 and 15.0 (owl1), 16.0 to 19.0 (owl2) and 20.0 (owl3, a new stack written for Owl 3).
- Odoo 20: modules keep their `ir.model.access.csv` and `ir.rule` records, turned into the `ir.access` rows that give the same access; a rule Odoo 20 cannot say that way is named in the server log. `get_param` / `set_param` answer as before; Font Awesome icons draw again.
- Odoo 16: lists get a gear button with the tools other modules register. On Odoo 17 and later the import review and result screens open again.
- Security: the "include secrets?" export question only runs the export that opened it; a user can no longer point it at another model or method. New helpers in `utils/compat.py`: `binary_bytes`, `content_disposition`; exported files are saved through `raw`.

## owl1-1.2.56_owl2-1.2.65 (2026-11-04)

- Store page: a new 2:1 thumbnail, so the Odoo Apps listing no longer crops the sides of the banner.

## owl1-1.2.55_owl2-1.2.64 (2026-11-04)

- Store page: a new banner that says what the module is and which Odoo series are tested (14.0 and 19.0). The image is much smaller.

## owl1-1.2.54_owl2-1.2.63 (2026-11-02)

- First Odoo test: it opens the web client and fails on any JavaScript error. It needs Chrome; without it Odoo skips the test.
- Store page and README explain this test.

## owl1-1.2.53_owl2-1.2.62 (2026-11-02)

- First public release. The shared base for every PNS module: install it first. The other modules depend on it; it depends on none of them.
- Views written the old way (`attrs`, `<tree>`) keep working on Odoo 17 and later. It also ships a small library: one name for helpers Odoo renamed between versions, toasts and reports, portable import/export, PDF and picture helpers, a full-screen picture viewer and an operation-result wizard.
- Security: the export wizard only deletes the exported file of the user who made it, not any attachment.
- Translations: "Warnings" and "Errors" in operation reports are translated, and on Odoo 19 the Python and JavaScript texts of the module load their translation.
