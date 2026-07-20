# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Dashboard",
    "version": "19.0.1.26.0",
    "website": "https://simetri-sinergi.id",
    "author": "OpenSynergy Indonesia, PT. Simetri Sinergi Indonesia",
    "contributors": [
        "Andhitia Rama <andhitia.r@gmail.com>",
    ],
    "license": "AGPL-3",
    "installable": True,
    "application": True,
    "depends": [
        "ssi_master_data_mixin",
    ],
    "data": [
        "security/ir_module_category_data.xml",
        "security/res_groups/dashboard.xml",
        "security/ir_model_access/dashboard_dashboard.xml",
        "security/ir_model_access/dashboard_data_source.xml",
        "security/ir_model_access/dashboard_color_scheme.xml",
        "security/ir_model_access/dashboard_import.xml",
        "security/ir_model_access/dashboard_item_move.xml",
        "security/ir_model_access/dashboard_template.xml",
        "security/ir_model_access/dashboard_create_from_template.xml",
        "security/ir_rule/dashboard_dashboard.xml",
        "security/ir_rule/dashboard_data_source.xml",
        "menu.xml",
        "views/dashboard_data_source.xml",
        "views/dashboard_color_scheme.xml",
        "views/dashboard_item.xml",
        "views/dashboard_dashboard.xml",
        "views/dashboard_template.xml",
        "wizard/dashboard_import_views.xml",
        "wizard/dashboard_item_move_views.xml",
        "wizard/dashboard_create_from_template_views.xml",
        "data/dashboard_dashboard_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ssi_dashboard/static/src/dashboard_action/*",
            "ssi_dashboard/static/src/dashboard_filter_bar/*",
            "ssi_dashboard/static/src/dashboard_grid/*",
            "ssi_dashboard/static/src/dashboard_item/*",
            "ssi_dashboard/static/src/dashboard_item_fallback/*",
            "ssi_dashboard/static/src/dashboard_item_preview/*",
            "ssi_dashboard/static/src/dashboard_layout_editor/*",
        ],
        "web.assets_tests": [
            "ssi_dashboard/static/tests/tours/*",
        ],
    },
}
