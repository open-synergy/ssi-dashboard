# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Dashboard Item - List",
    "version": "19.0.1.1.0",
    "website": "https://simetri-sinergi.id",
    "author": "OpenSynergy Indonesia, PT. Simetri Sinergi Indonesia",
    "contributors": [
        "Andhitia Rama <andhitia.r@gmail.com>",
    ],
    "license": "AGPL-3",
    "installable": True,
    "application": False,
    "depends": [
        "ssi_dashboard",
    ],
    "data": [
        "security/ir_model_access/dashboard_item_column.xml",
        "views/dashboard_item.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ssi_dashboard_item_list/static/src/dashboard_item_list/*",
        ],
    },
}
