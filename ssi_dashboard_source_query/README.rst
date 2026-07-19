.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

============================
Dashboard Source - SQL Query
============================

Adds the ``query`` data source type to the SSI Dashboard framework: dashboard items
pull their rows from a raw SQL ``SELECT`` statement written by a dashboard
administrator, through the same ``dashboard.data_source`` used by the ``orm`` type
shipped by ``ssi_dashboard``. This covers analytical questions that span more than one
model at once (e.g. an aging report crossing invoices and payments), which cannot be
expressed as a single ``_read_group`` call.

**The query is executed with full database privileges.** The ``Query`` field is
readable and editable only by the Dashboard Administrator group, at the ORM level —
not just hidden in the form view — because whoever can write to it can read (and, if
careless, write to) anything the database user Odoo connects with can reach. Only
grant the Dashboard Administrator group to trusted users.

Before it ever runs, ``Query`` is checked to start with the keyword ``SELECT`` and to
contain no semicolon other than a single trailing one, so it cannot be used to stack a
second statement after the ``SELECT``. It then runs inside its own ``SAVEPOINT`` under
a 10-second statement timeout, so a failing or slow query does not affect the rest of
the transaction or hang the worker. ``Query`` may reference the named parameters
``%(date_start)s``, ``%(date_end)s``, ``%(uid)s`` and ``%(company_id)s``; every value
is passed to the database as a bind parameter, never concatenated into the SQL text.
A result column named ``group_label`` is used as the row's group label, so a chart or
table can bind to a ``query`` data source the same way it binds to any other type.


Installation
============

To install this module, you need to:

1.  Clone the branch 19.0 of the repository https://github.com/open-synergy/ssi-dashboard
2.  Add the path to this repository in your configuration (addons-path)
3.  Update the module list (Must be on developer mode)
4.  Go to menu *Apps -> Apps -> Main Apps*
5.  Search For *Dashboard Source - SQL Query*
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
