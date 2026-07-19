.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

=====================
Dashboard Item - List
=====================

Adds the ``list`` dashboard item type to the SSI Dashboard framework: the item's
fetched data rendered as a table, with columns configured in the item's ``Config``
JSON field, through an OWL component registered under
``registry.category("ssi_dashboard.item_widgets")``.

The table reads ``columns`` (required — a list of objects naming a ``key``, the row
key rendered in that column, and, optionally, a ``label`` defaulting to ``key`` as-is
when empty) and ``limit`` (optional Integer, 1-100, defaulting to 10 — the maximum
number of rows rendered) out of the item's ``Config`` JSON field, e.g.
``{"columns": [{"key": "name"}, {"key": "amount", "label": "Amount"}], "limit": 20}``.
The row limit is enforced server-side, before the payload is sent to the browser, so a
data source that returns far more rows than fit on screen never reaches the browser. A
row missing one of the configured columns' keys renders as an empty cell rather than an
error, since non-ORM data sources (API, ODBC) do not guarantee a uniform row shape.
Table colors follow the dashboard's own color scheme through CSS custom properties;
this module carries no palette of its own.


Installation
============

To install this module, you need to:

1.  Clone the branch 19.0 of the repository https://github.com/open-synergy/ssi-dashboard
2.  Add the path to this repository in your configuration (addons-path)
3.  Update the module list (Must be on developer mode)
4.  Go to menu *Apps -> Apps -> Main Apps*
5.  Search For *Dashboard Item - List*
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
