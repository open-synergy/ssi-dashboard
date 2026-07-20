# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
"""Drop ``dashboard_item.config`` (Text, raw JSON), the field this module
used before dedicated columns existed for each item ``type``.

No data is moved by this script -- there is nothing left to move. Each
item-type module (``ssi_dashboard_item_chart``, ``ssi_dashboard_item_list``,
``ssi_dashboard_item_tile``) already migrated its own reads of ``self.config``
to real fields in open-synergy/ssi-dashboard#28, #29 and #31, and the last two
readers inside this module itself (``dashboard_item._prepare_export_item_vals``
and ``dashboard.import._import_one_item``) stopped touching the field earlier
in the same release that ships this script -- see
open-synergy/ssi-dashboard#53.

Runs as ``pre-migrate`` so the column is gone before Odoo's schema sync for
this module runs.
"""


def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    if not version:
        # Fresh install, nothing to migrate.
        return
    if not _column_exists(cr, "dashboard_item", "config"):
        # Already migrated, or 'config' never existed on this database.
        return
    cr.execute("ALTER TABLE dashboard_item DROP COLUMN config")
