import {registry} from "@web/core/registry";

/**
 * Tour behind tests/test_dashboard_print_tour.py's
 * "test_print_mode_hides_chrome_and_shows_title" — backlog issue #49,
 * Skenario Uji positif (P7/L-19: only reachable through `HttpCase`).
 *
 * Clicks the 'Print' button (".o_ssi_dashboard_print", only rendered
 * when "dashboard.allow_pdf_export" — see dashboard_action.esm.js) and
 * asserts the class it adds to the root element
 * (".o_ssi_dashboard_print_mode") actually hides the surrounding header/
 * filter bar (see dashboard_action.scss's "ssi-dashboard-print-layout"
 * mixin) while the print-only summary block shows this dashboard's own
 * title. Never calls "window.print()" itself — clicking the button does,
 * but headless Chrome (used by CI) does not display or block on the
 * native print dialog, so the tour keeps running straight through it.
 */
registry.category("web_tour.tours").add("ssi_dashboard_print_mode_tour", {
    steps: () => [
        {
            content: "Wait for the dashboard to load",
            trigger: ".o_ssi_dashboard_title",
        },
        {
            content: "The Print button is rendered (allow_pdf_export is True)",
            trigger: ".o_ssi_dashboard_print",
        },
        {
            content: "Click the Print button",
            trigger: ".o_ssi_dashboard_print",
            run: "click",
        },
        {
            content: "Print mode hides the header (backend chrome + action buttons)",
            trigger:
                ".o_ssi_dashboard.o_ssi_dashboard_print_mode " +
                ".o_ssi_dashboard_header:hidden",
        },
        {
            content: "Print mode hides the filter bar",
            trigger:
                ".o_ssi_dashboard.o_ssi_dashboard_print_mode " +
                ".o_ssi_dashboard_filter_bar:hidden",
        },
        {
            content: "Print-only summary shows the dashboard title",
            trigger:
                ".o_ssi_dashboard_print_summary:visible " +
                ".o_ssi_dashboard_print_title:contains(Print Mode Tour Dashboard)",
        },
    ],
});

/**
 * Tour behind
 * "test_print_button_hidden_when_allow_pdf_export_disabled" — backlog
 * issue #49, Skenario Uji negatif (P7/L-19).
 */
registry.category("web_tour.tours").add("ssi_dashboard_print_disabled_tour", {
    steps: () => [
        {
            content: "Wait for the dashboard to load",
            trigger: ".o_ssi_dashboard_title",
        },
        {
            content: "The Print button is not rendered (allow_pdf_export is False)",
            trigger: "body:not(:has(.o_ssi_dashboard_print))",
        },
    ],
});
