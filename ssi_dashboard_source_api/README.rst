.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

===========================
Dashboard Source - REST API
===========================

Adds the ``api`` data source type to the SSI Dashboard framework: dashboard items
pull their rows from an HTTP JSON endpoint instead of an Odoo model, through the same
``dashboard.data_source`` used by the ``orm`` type shipped by ``ssi_dashboard``.

The endpoint is configured on ``Data Source`` (``GET``/``POST``, optional Basic /
Bearer Token / Custom Header authentication, JSON body for ``POST``, a dotted path to
the list of rows inside the response, and a request timeout). Credential fields
(``API Password``, ``API Token``) are readable and editable only by the Dashboard
Administrator group at the ORM level, not just hidden in the form view. Every failure
mode — missing URL, connection error, timeout, HTTP status >= 400, an invalid JSON
response, or a result path that does not resolve to a list — is raised as a readable
error message that never includes a credential value.


Installation
============

To install this module, you need to:

1.  Clone the branch 19.0 of the repository https://github.com/open-synergy/ssi-dashboard
2.  Add the path to this repository in your configuration (addons-path)
3.  Update the module list (Must be on developer mode)
4.  Go to menu *Apps -> Apps -> Main Apps*
5.  Search For *Dashboard Source - REST API*
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
