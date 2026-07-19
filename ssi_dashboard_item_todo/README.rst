.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

======================
Dashboard Item - To Do
======================

Adds the ``todo`` dashboard item type to the SSI Dashboard framework: a checklist
made of ``Section`` headings and checkable ``Task`` rows, rendered by an OWL
component registered under ``registry.category("ssi_dashboard.item_widgets")``.
Unlike every other item type, ``todo`` needs no ``Data Source`` at all — the core
``dashboard.item.data_source_id`` field becomes optional depending on
``_is_data_source_required()``, and this module is the first to override it.

Each row is a real record of model ``dashboard.item.todo`` (field ``To Do Rows``
on the item), not a JSON blob:

* ``Line Type`` — ``Section`` (a heading, ignores ``Done``) or ``Task`` (a
  checkable row).
* ``Done`` — ticked state of a ``Task`` row, toggled by the browser through the
  ``toggle_todo_done`` method (also callable by a regular ``Dashboard / User``,
  not just an administrator).


Installation
============

To install this module, you need to:

1.  Clone the branch 19.0 of the repository https://github.com/open-synergy/ssi-dashboard
2.  Add the path to this repository in your configuration (addons-path)
3.  Update the module list (Must be on developer mode)
4.  Go to menu *Apps -> Apps -> Main Apps*
5.  Search For *Dashboard Item - To Do*
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
