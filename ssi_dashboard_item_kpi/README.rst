.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

====================
Dashboard Item - KPI
====================

Adds the ``kpi`` dashboard item type to the SSI Dashboard framework: a realized
value shown side by side with either its target or a comparison period, rendered
by an OWL component registered under
``registry.category("ssi_dashboard.item_widgets")``. The aggregation itself
(measure/aggregate, grouping, comparison, target) is entirely computed by the
core ``dashboard.item``/``dashboard.data_source`` — this module only reads the
first row/first measure of what is already fetched and computes the achievement
percentage and movement direction.

Each KPI item is configured through real fields, not a JSON blob:

* ``KPI Layout`` — one of two arrangements: ``KPI With Target`` compares
  ``Value`` against today's target and requires ``Goal Type`` to be set to
  something other than ``No Target``; ``Data Comparison`` compares ``Value``
  against the first comparison range of ``Data Source`` and requires ``Data
  Source``'s ``Comparison`` to be set to something other than ``No
  Comparison``.
* ``KPI Display`` — shape of the comparison number shown alongside ``Value``:
  ``Number``, ``Percentage`` or ``Ratio``.
* ``Invert Direction`` — tick when a decrease in ``Value`` is actually an
  improvement (e.g. a count of complaints), so the movement marker is flipped.


Installation
============

To install this module, you need to:

1.  Clone the branch 19.0 of the repository https://github.com/open-synergy/ssi-dashboard
2.  Add the path to this repository in your configuration (addons-path)
3.  Update the module list (Must be on developer mode)
4.  Go to menu *Apps -> Apps -> Main Apps*
5.  Search For *Dashboard Item - KPI*
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
