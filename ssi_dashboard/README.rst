.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

=========
Dashboard
=========

Core module of the SSI Dashboard framework. Provides the ``dashboard.dashboard``,
``dashboard.item``, ``dashboard.data_source`` and ``dashboard.color_scheme`` models,
with three extension seams (item type, data source type, color scheme) that other
modules build on without editing this one: new tile kinds add a
``dashboard.item.type`` selection value plus a matching
``_prepare_render_payload_<type>`` method, new data feeds add a
``dashboard.data_source.type`` selection value plus a matching
``_fetch_data_<type>`` method, and new palettes are just
``dashboard.color_scheme`` records.

This module ships one built-in data source type (``orm``, reading an Odoo model
through ``read_group``) and one built-in item type (``placeholder``) so it can be
installed and tested standalone.


Installation
============

To install this module, you need to:

1.  Clone the branch 19.0 of the repository https://github.com/open-synergy/ssi-dashboard
2.  Add the path to this repository in your configuration (addons-path)
3.  Update the module list (Must be on developer mode)
4.  Go to menu *Apps -> Apps -> Main Apps*
5.  Search For *Dashboard*
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
