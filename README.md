

# Dashboard
<!-- /!\ Non OCA Context : Set here the badge of your runbot / runboat instance. -->
[![Pre-commit Status](https://github.com/open-synergy/ssi-dashboard/actions/workflows/pre-commit.yml/badge.svg?branch=19.0)](https://github.com/open-synergy/ssi-dashboard/actions/workflows/pre-commit.yml?query=branch%3A19.0)
[![Build Status](https://github.com/open-synergy/ssi-dashboard/actions/workflows/test.yml/badge.svg?branch=19.0)](https://github.com/open-synergy/ssi-dashboard/actions/workflows/test.yml?query=branch%3A19.0)
[![codecov](https://codecov.io/gh/open-synergy/ssi-dashboard/branch/19.0/graph/badge.svg)](https://codecov.io/gh/open-synergy/ssi-dashboard)
<!-- /!\ Non OCA Context : Set here the badge of your translation instance. -->

<!-- /!\ do not modify above this line -->

The SSI Dashboard framework lets a user compose a dashboard out of items (tiles,
charts, lists, ...) that each pull their data from a reusable data source, and
style the whole dashboard with a shared color scheme. The framework is closed for
modification and open for extension: the core module (`ssi_dashboard`) owns the
`dashboard.dashboard`, `dashboard.item`, `dashboard.data_source` and
`dashboard.color_scheme` models plus their dispatch logic, while every other
module in this repository only adds a new choice to one of the extension points
below — none of them change `ssi_dashboard` itself.

## Extension points

- **Item type** — `dashboard.item.type`, a `Selection` field on `dashboard.item`.
  A new tile kind adds a value via `selection_add`, ships an OWL component
  registered under `registry.category("ssi_dashboard.item_widgets")` for that
  value so the browser knows how to render it, and may implement a matching
  `_prepare_render_payload_<type>` method to enrich the server-side payload.
- **Data source type** — `dashboard.data_source.type`, a `Selection` field on
  `dashboard.data_source`. A new feed kind adds a value via `selection_add` and
  implements the matching `_fetch_data_<type>` method; the `_fetch_data`
  dispatcher on `dashboard.data_source` stays untouched.
- **Color scheme** — `dashboard.color_scheme` is plain master data, no
  type/registry involved. A new palette is just a `dashboard.color_scheme`
  record with `dashboard.color_scheme.color` rows; `_prepare_css_variables`
  turns them into CSS custom properties for the browser.

## Addons

module | summary | depends
--- | --- | ---
[ssi_dashboard](ssi_dashboard/) | Dashboard | ssi_master_data_mixin
[ssi_dashboard_color_scheme_ssi](ssi_dashboard_color_scheme_ssi/) | Dashboard Color Scheme - SSI | ssi_dashboard
[ssi_dashboard_item_chart](ssi_dashboard_item_chart/) | Dashboard Item - Chart | ssi_dashboard
[ssi_dashboard_item_list](ssi_dashboard_item_list/) | Dashboard Item - List | ssi_dashboard
[ssi_dashboard_item_tile](ssi_dashboard_item_tile/) | Dashboard Item - Tile | ssi_dashboard
[ssi_dashboard_source_api](ssi_dashboard_source_api/) | Dashboard Source - REST API | ssi_dashboard

<!-- /!\ do not modify below this line -->

<!-- prettier-ignore-start -->

[//]: # (addons)

Available addons
----------------
addon | version | maintainers | summary
--- | --- | --- | ---
[ssi_dashboard](ssi_dashboard/) | 19.0.1.2.0 |  | Dashboard
[ssi_dashboard_color_scheme_ssi](ssi_dashboard_color_scheme_ssi/) | 19.0.1.0.1 |  | Dashboard Color Scheme - SSI
[ssi_dashboard_item_chart](ssi_dashboard_item_chart/) | 19.0.1.0.0 |  | Dashboard Item - Chart
[ssi_dashboard_item_list](ssi_dashboard_item_list/) | 19.0.1.0.0 |  | Dashboard Item - List
[ssi_dashboard_item_tile](ssi_dashboard_item_tile/) | 19.0.1.0.0 |  | Dashboard Item - Tile
[ssi_dashboard_source_api](ssi_dashboard_source_api/) | 19.0.1.0.0 |  | Dashboard Source - REST API

[//]: # (end addons)

<!-- prettier-ignore-end -->

## Licenses

This repository is licensed under [AGPL-3.0](LICENSE).

However, each module can have a totally different license, as long as they adhere to PT. Simetri Sinergi Indonesia
policy. Consult each module's `__manifest__.py` file, which contains a `license` key
that explains its license.

----
<!-- /!\ Non OCA Context : Set here the full description of your organization. -->
