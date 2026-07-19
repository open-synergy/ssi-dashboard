.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

=====================
Dashboard Item - Tile
=====================

Adds the ``tile`` dashboard item type to the SSI Dashboard framework: a single
aggregate number, with its label, rendered by an OWL component registered under
``registry.category("ssi_dashboard.item_widgets")``. The aggregation itself
(measure/aggregate, grouping, comparison, target) is entirely computed by the
core ``dashboard.item``/``dashboard.data_source`` — this module only formats and
decorates the first row of the item's fetched data.

Each tile item is configured through real fields, not a JSON blob:

* ``Tile Layout`` — one of six arrangements: Value Only, Value With Icon, Value
  With Comparison, Value With Target, Value With Sparkline, Value With
  Background Icon. ``Value With Comparison`` requires the data source's
  ``Comparison`` to be set; ``Value With Target`` requires the item's
  ``Goal Type`` to be set.
* ``Tile Icon`` — a Font Awesome icon class already bundled with the Odoo
  backend, e.g. ``fa-shopping-cart``.
* ``Tile Background Color`` / ``Tile Text Color`` — CSS color values. Left
  empty, the dashboard's own ``--ssi-dashboard-surface`` /
  ``--ssi-dashboard-text`` color scheme variables are used instead.


Installation
============

To install this module, you need to:

1.  Clone the branch 19.0 of the repository https://github.com/open-synergy/ssi-dashboard
2.  Add the path to this repository in your configuration (addons-path)
3.  Update the module list (Must be on developer mode)
4.  Go to menu *Apps -> Apps -> Main Apps*
5.  Search For *Dashboard Item - Tile*
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
