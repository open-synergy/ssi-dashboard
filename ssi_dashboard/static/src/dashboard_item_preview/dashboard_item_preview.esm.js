import {Component, useState} from "@odoo/owl";
import {DashboardItem} from "../dashboard_item/dashboard_item.esm";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {standardWidgetProps} from "@web/views/widgets/standard_widget_props";
import {useDebounced} from "@web/core/utils/timing";
import {useRecordObserver} from "@web/model/relational_model/utils";
import {useService} from "@web/core/utils/hooks";

/**
 * "dashboard.item" fields shown on "ssi_dashboard.dashboard_item_view_form"
 * (see views/dashboard_item.xml) that feed the live preview below. Every
 * other field of the item (its "type", "data_source_id", layout, ...) is
 * not editable from that form, so it is left out of "vals" on purpose —
 * preview_render_payload() (models/dashboard_item.py) falls back to this
 * item's own already-saved value for anything missing from "vals",
 * through its "new(vals, origin=self)" call. "goal_ids" is left out too:
 * it is a nested one2many edited inline in the same form, and the
 * preview keeps reflecting this item's already-saved goal rows until
 * they are actually saved.
 */
const PREVIEW_FIELD_NAMES = [
    "name",
    "goal_type",
    "goal_value",
    "multiplier",
    "number_format",
    "precision_digits",
    "unit_type",
    "currency_id",
    "unit_text",
    "unit_position",
    "item_theme",
    "item_header_color",
    "item_border_color",
];

/**
 * View widget (not a field widget — see "standardWidgetProps") embedded
 * in "ssi_dashboard.dashboard_item_view_form" via
 * <widget name="ssi_dashboard.item_preview"/> so the quick-edit dialog
 * opened by DashboardAction.onEditItemClick() shows a live preview of
 * the tile while the form is still being edited, before 'Save' is ever
 * pressed.
 *
 * Reuses DashboardItem itself to render the preview tile, so the
 * preview is guaranteed to look exactly like the real dashboard: both
 * go through the same "ssi_dashboard.item_widgets" registry lookup and
 * the same theme styling. "isAdmin"/"onEditClick" are left unset on
 * purpose — DashboardItem treats both as optional — so the preview
 * tile never shows its own 'Edit' button.
 *
 * Known limitation: "item_theme" values other than "custom" resolve to
 * "var(--ssi-dashboard-<name>)", a CSS custom property normally set on
 * the real dashboard's own root element (DashboardAction's "rootStyle",
 * built from the dashboard's color scheme). This dialog is not rendered
 * inside that root element, so those variables are undefined here and
 * the swatch falls back to transparent — only the numeric/text parts
 * of the preview are guaranteed accurate. "custom" colors are literal
 * values and always render correctly.
 */
export class DashboardItemPreview extends Component {
    static template = "ssi_dashboard.DashboardItemPreview";
    static components = {DashboardItem};
    static props = {...standardWidgetProps};

    setup() {
        this.orm = useService("orm");
        this.state = useState({item: null, error: null});
        this.refreshDebounced = useDebounced(
            (record) => this.refreshPreview(record),
            400
        );
        useRecordObserver((record) => this.refreshDebounced(record));
    }

    /**
     * @param {Object} record "props.record"-shaped relational model
     *  record, passed through by useRecordObserver()/the debounced
     *  wrapper so this always reads the form's latest values even
     *  though the call itself was delayed.
     * @returns {Object} vals ready for orm.call — many2one values in
     *  "record.data" are "{id, display_name}"-like objects, unwrapped
     *  here to their bare id (or "false" when empty) since that is
     *  the shape preview_render_payload()/write() expect.
     */
    buildPreviewVals(record) {
        const vals = {};
        for (const name of PREVIEW_FIELD_NAMES) {
            const value = record.data[name];
            vals[name] = value && typeof value === "object" ? value.id : value;
        }
        return vals;
    }

    async refreshPreview(record) {
        const payload = await this.orm.call(
            "dashboard.item",
            "preview_render_payload",
            [[record.resId], this.buildPreviewVals(record)]
        );
        if (payload.error) {
            this.state.error = payload.error;
            this.state.item = null;
        } else {
            this.state.error = null;
            this.state.item = payload;
        }
    }

    get previewLabel() {
        return _t("Preview");
    }
}

export const dashboardItemPreview = {
    component: DashboardItemPreview,
};

registry
    .category("view_widgets")
    .add("ssi_dashboard.item_preview", dashboardItemPreview);
