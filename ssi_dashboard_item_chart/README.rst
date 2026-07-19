.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

======================
Dashboard Item - Chart
======================

Adds the ``chart`` dashboard item type to the SSI Dashboard framework: a bar,
line or pie chart rendered by an OWL component registered under
``registry.category("ssi_dashboard.item_widgets")``, built on Odoo's own
bundled Chart.js (``web.chartjs_lib``) — no extra chart library is vendored.

The chart reads ``chart_type`` (one of ``bar``, ``line``, ``pie``, defaulting
to ``bar``), ``group_by`` (required — the field name rows are bucketed by)
and ``measure`` (optional — the field name summed per group; each group is
counted instead when empty) out of the item's ``Config`` JSON field, e.g.
``{"chart_type": "line", "group_by": "state", "measure": "amount"}``. Series
colors follow the dashboard's own color scheme through
``--ssi-dashboard-chart-1`` .. ``--ssi-dashboard-chart-8`` CSS custom
properties; this module carries no palette of its own.


Installation
============

To install this module, you need to:

1.  Clone the branch 19.0 of the repository https://github.com/open-synergy/ssi-dashboard
2.  Add the path to this repository in your configuration (addons-path)
3.  Update the module list (Must be on developer mode)
4.  Go to menu *Apps -> Apps -> Main Apps*
5.  Search For *Dashboard Item - Chart*
6.  Install the module


Bug Tracker
===========

Bugs are tracked on `GitHub Issues
<https://github.com/open-synergy/ssi-dashboard/issues>`_. In case of trouble, please
check there if your issue has already been reported. If you spotted it first,
help us smash it by providing detailed and welcomed feedback.


Credits
=======

Contributors
------------

* Andhitia Rama <andhitia.r@gmail.com>

Maintainer
----------

.. image:: https://simetri-sinergi.id/logo.png
   :alt: PT. Simetri Sinergi Indonesia
   :target: https://simetri-sinergi.id

This module is maintained by the PT. Simetri Sinergi Indonesia.
