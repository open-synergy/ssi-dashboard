.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

======================
Dashboard Item - Chart
======================

Adds the ``chart`` dashboard item type to the SSI Dashboard framework: a chart
rendered by an OWL component registered under
``registry.category("ssi_dashboard.item_widgets")``, built on Odoo's own
bundled Chart.js (``web.chartjs_lib``) — no extra chart library is vendored.

Seven chart kinds are supported (``chart_type``, defaulting to ``bar``): Bar,
Horizontal Bar, Line, Area, Pie, Doughnut and Polar Area. Grouping and
measures are entirely configured on the item's ``Data Source`` through its
own real fields (``Group By Field``, ``Sub Group By Field``, ``Measure
Field``/``Measures``) — this module reads no ``Config`` JSON. A data source
with a ``Sub Group By Field`` produces one dataset per second-dimension
value; a data source with several ``Measures`` and no second dimension
produces one dataset per measure instead — the two cannot be combined, since
that would make the resulting datasets ambiguous. A ``chart`` item requires
its data source to have a ``Group By Field`` set. Series colors follow the
dashboard's own color scheme through ``--ssi-dashboard-chart-1`` ..
``--ssi-dashboard-chart-8`` CSS custom properties; this module carries no
palette of its own.

Composition and readability options are available on top of the seven chart
kinds: ``chart_stacked`` stacks datasets on Bar/Horizontal Bar/Area charts,
``chart_semi_circle`` draws Pie/Doughnut charts as a half circle,
``chart_cumulative`` adds one extra dataset with the running cumulative
total of the chart's first dataset (always drawn as a line, not available
on Pie/Doughnut/Polar Area), and ``chart_data_label`` shows each data
point's value or percentage-of-series-total directly on the chart.


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
