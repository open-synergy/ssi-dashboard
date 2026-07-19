import {Component} from "@odoo/owl";

/**
 * Placeholder shown for a dashboard item whose "type" has no component
 * registered under registry.category("ssi_dashboard.item_widgets") — this
 * core module ships no concrete item type, so every "placeholder" item
 * (the only type this module defines) renders through here. Extension
 * modules that register a component for their own type stop seeing this
 * fallback for that type.
 */
export class DashboardItemFallback extends Component {
    static template = "ssi_dashboard.DashboardItemFallback";
    static props = {item: Object};
}
