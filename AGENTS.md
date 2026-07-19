# Agent Instructions — ssi-dashboard

This file is intended for **AI assistants** (GitHub Copilot, Claude, Cursor, ChatGPT,
and similar tools) working inside this repository.

`ssi-dashboard` implements the SSI Dashboard framework: a small core module
(`ssi_dashboard`) that owns the `dashboard.dashboard`, `dashboard.item`,
`dashboard.data_source` and `dashboard.color_scheme` models, plus a set of extension
modules that each add a single item type, data source type, or color scheme without ever
modifying the core module's code. The list of modules and the contract for each of the
three extension points are documented in [`README.md`](README.md) — read that file first
for an up-to-date overview; this file does not repeat it.

---

## User Guide (Work Instructions)

Each module can have a `docs/` directory containing **Work Instructions (IK)** —
step-by-step operational documentation for using the feature from the user's
perspective, stored under:

```
<module_name>/docs/<model_name>/<number>-<action>.md
```

No module in this repository has a `docs/` directory yet — no Work Instruction has been
written so far. Do not fabricate one; when a user asks how to operate a feature and no
matching file exists under `docs/`, say so explicitly instead of guessing the steps.

### How to Answer User Questions About Feature Usage

1. Identify the feature being asked about.
2. Look for a matching Work Instruction under `<module_name>/docs/<model_name>/` in the
   module that owns the feature (see [`README.md`](README.md) for the module list).
3. **Read that file** before answering — do not fabricate steps from assumptions.
4. If a relevant extension module is installed (e.g. an item type or data source type
   module), also read its Work Instruction, if any, and **merge** it with the base
   module's IK.
5. Answer based on the content of the Work Instruction. If none exists yet, say so
   instead of inventing one.

---

## Extending the Framework

Adding a new item type, data source type, or color scheme means creating a new module
that depends on `ssi_dashboard` (or on the module that owns the type being extended) and
implements exactly one of the three extension points described in
[`README.md`](README.md) — do not add fields or methods to `ssi_dashboard` itself to
support a new type. Before writing such a module, read the extension point's contract in
`README.md` and inspect an existing sibling module (e.g. `ssi_dashboard_item_tile` for
an item type, `ssi_dashboard_source_api` for a data source type) as a concrete
reference.

---

## Module Development Guidelines

For code conventions, file structure, naming, security, views, and other SSI standard
patterns, follow the SSI Odoo development guidelines.
