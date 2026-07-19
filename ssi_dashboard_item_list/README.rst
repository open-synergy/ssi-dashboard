.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

=====================
Dashboard Item - List
=====================

Adds the ``list`` dashboard item type to the SSI Dashboard framework: the item's
fetched data rendered as a table, through an OWL component registered under
``registry.category("ssi_dashboard.item_widgets")``.

Columns are configured through a real ``Columns`` (``dashboard.item.column``) list on
the item — no ``Config`` JSON field is read anywhere in this module. Each column names
a ``Key`` (the row key it reads its value from), a ``Name`` (its header) and a
``Column Type``: ``Text``, ``Number`` (formatted following the item's own number
format configuration), or ``Deviation From Target`` (``Key``'s numeric value minus the
item's target for the row's date — requires ``Goal Type`` to not be ``No Target``). A
row missing one of the configured columns' keys renders as an empty cell rather than
an error, since non-ORM data sources (API, ODBC) do not guarantee a uniform row shape.

``List Mode`` toggles between ``Flat`` (rows as returned) and ``Grouped`` (rows
arranged under their data source's ``Group By Field`` value, with a subtotal row per
group — requires ``Group By Field`` to be set on ``Data Source``). ``Page Size``
(1-200, default 10) tells the browser how many already-fetched rows to show per page —
pagination happens client-side, over rows already sent; it does not change how many
rows ``Data Source``'s own ``Limit`` fetches from the database. Table colors follow
the dashboard's own color scheme through CSS custom properties; this module carries no
palette of its own.


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
