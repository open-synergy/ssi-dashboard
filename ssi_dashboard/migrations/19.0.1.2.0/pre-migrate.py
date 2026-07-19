# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
"""Move ``dashboard_data_source.config`` (JSON, ``measure``/``aggregate``/
``group_by``/``limit`` keys) into the real columns added in this version:
``measure_field_id``, ``aggregate``, ``group_by_field_id`` and ``limit``.

Runs as ``pre-migrate`` (before Odoo's schema sync for this module), so the
new columns do not exist yet in the database -- they are created here with
plain SQL, populated from the old JSON, and Odoo's own ``_auto_init`` later
finds them already in place (matching type) and only adds the FK
constraints for the two ``Many2one`` fields.

Does **not** touch ``dashboard_item.config`` -- that field is not removed
by this version (see open-synergy/ssi-dashboard#18 and its follow-up #53).
"""
import json
import logging

_logger = logging.getLogger(__name__)

_TABLE = "dashboard_data_source"
_VALID_AGGREGATES = ("count", "sum", "avg", "min", "max")
_DEFAULT_AGGREGATE = "count"


def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def _add_column_if_missing(cr, table, column, column_type):
    if not _column_exists(cr, table, column):
        cr.execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {column_type}')


def _field_id(cr, model_id, field_name):
    """Look up the ``ir.model.fields`` id for `field_name` on `model_id`."""
    if not model_id or not field_name:
        return None
    cr.execute(
        "SELECT id FROM ir_model_fields WHERE model_id = %s AND name = %s",
        (model_id, field_name),
    )
    row = cr.fetchone()
    return row[0] if row else None


def migrate(cr, version):
    if not version:
        # Fresh install, nothing to migrate.
        return
    if not _column_exists(cr, _TABLE, "config"):
        # Already migrated, or 'config' never existed on this database.
        return

    _add_column_if_missing(cr, _TABLE, "measure_field_id", "integer")
    _add_column_if_missing(cr, _TABLE, "aggregate", "varchar")
    _add_column_if_missing(cr, _TABLE, "group_by_field_id", "integer")
    _add_column_if_missing(cr, _TABLE, "limit", "integer")

    cr.execute(
        f'SELECT id, model_id, config FROM "{_TABLE}" '
        "WHERE config IS NOT NULL AND config != ''"
    )
    rows = cr.fetchall()
    for row_id, model_id, config_text in rows:
        try:
            config = json.loads(config_text)
        except ValueError:
            _logger.warning(
                "%s id=%s has invalid JSON in 'config', skipped by migration",
                _TABLE,
                row_id,
            )
            continue
        if not isinstance(config, dict):
            continue
        measure_field_id = _field_id(cr, model_id, config.get("measure"))
        group_by_field_id = _field_id(cr, model_id, config.get("group_by"))
        aggregate = config.get("aggregate") or _DEFAULT_AGGREGATE
        if aggregate not in _VALID_AGGREGATES:
            aggregate = _DEFAULT_AGGREGATE
        limit = config.get("limit") or 0
        cr.execute(
            f'UPDATE "{_TABLE}" SET measure_field_id = %s, aggregate = %s, '
            'group_by_field_id = %s, "limit" = %s WHERE id = %s',
            (measure_field_id, aggregate, group_by_field_id, limit, row_id),
        )
