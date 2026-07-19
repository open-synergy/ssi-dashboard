import {Component, useRef, useState} from "@odoo/owl";
import {
    GRID_COLUMNS,
    clampGrid,
    gridColumnStep,
    gridRowStep,
} from "../dashboard_grid/dashboard_grid_constants.esm";
import {_t} from "@web/core/l10n/translation";

/**
 * Drag-and-resize layout editor shown instead of the read-only item grid
 * (see ../dashboard_action/dashboard_action.esm.js) while a dashboard
 * administrator arranges positions/sizes. Seret (drag) and ubah-ukuran
 * (resize) are implemented with native pointer events over the same CSS
 * grid the read-only view uses — no external grid library.
 *
 * Props:
 *  - items: seed layout — one entry per dashboard.item, each
 *    {id, name, column_start, row_start, column_width, row_height}.
 *    Built by DashboardAction.onEditLayoutClick(), which already
 *    resolves the "flowing placement" starting positions when needed —
 *    this component only ever works with explicit coordinates.
 *  - onSave: (layout) => any, called with the current
 *    [{id, column_start, row_start, column_width, row_height}, ...]
 *    when 'Save' is pressed.
 *  - onCancel: () => any, called when 'Cancel' is pressed. This
 *    component never calls the server itself — discarding its local
 *    state is enough to "cancel", since the read-only grid it replaced
 *    was never touched.
 */
export class DashboardLayoutEditor extends Component {
    static template = "ssi_dashboard.DashboardLayoutEditor";
    static props = {
        items: Array,
        onSave: Function,
        onCancel: Function,
    };

    setup() {
        this.gridRef = useRef("grid");
        this.state = useState({
            layout: this.props.items.map((item) => ({...item})),
        });
    }

    get saveLabel() {
        return _t("Save");
    }

    get cancelLabel() {
        return _t("Cancel");
    }

    get hintLabel() {
        return _t("Drag a tile to move it, or its bottom-right handle to resize it.");
    }

    /**
     * @param {Number} tileId
     * @returns {Object} the "state.layout" entry for "tileId".
     */
    tileById(tileId) {
        return this.state.layout.find((tile) => tile.id === tileId);
    }

    /**
     * @param {Object} tile one "state.layout" entry.
     * @returns {String} inline "style" placing "tile" at its current
     *  explicit coordinates — same shape as DashboardItem's own "style"
     *  getter with "useExplicitPosition" true, see
     *  ../dashboard_item/dashboard_item.esm.js.
     */
    tileStyle(tile) {
        return (
            `grid-column: ${tile.column_start + 1} / span ${tile.column_width}; ` +
            `grid-row: ${tile.row_start + 1} / span ${tile.row_height};`
        );
    }

    /**
     * Pointer-drag handler moving a tile: pressing anywhere on the tile
     * except its resize handle changes "column_start"/"row_start" as
     * the pointer moves, clamped so the tile never leaves the grid's 12
     * columns or goes above row 0. Uses pointer capture on the tile
     * itself so the drag keeps tracking even when the pointer leaves
     * the tile's bounds.
     *
     * @param {PointerEvent} ev
     * @param {Number} tileId
     */
    onTilePointerDown(ev, tileId) {
        if (ev.button !== 0) {
            return;
        }
        ev.preventDefault();
        const tile = this.tileById(tileId);
        const startX = ev.clientX;
        const startY = ev.clientY;
        const startColumnStart = tile.column_start;
        const startRowStart = tile.row_start;
        const columnStep = gridColumnStep(this.gridRef.el.getBoundingClientRect().width);
        const rowStep = gridRowStep();
        const target = ev.currentTarget;
        target.setPointerCapture(ev.pointerId);
        const onMove = (moveEv) => {
            const deltaColumns = Math.round((moveEv.clientX - startX) / columnStep);
            const deltaRows = Math.round((moveEv.clientY - startY) / rowStep);
            tile.column_start = clampGrid(
                startColumnStart + deltaColumns,
                0,
                GRID_COLUMNS - tile.column_width
            );
            tile.row_start = Math.max(0, startRowStart + deltaRows);
        };
        const onUp = (upEv) => {
            target.releasePointerCapture(upEv.pointerId);
            target.removeEventListener("pointermove", onMove);
            target.removeEventListener("pointerup", onUp);
        };
        target.addEventListener("pointermove", onMove);
        target.addEventListener("pointerup", onUp);
    }

    /**
     * Pointer-drag handler resizing a tile from its bottom-right handle:
     * changes "column_width"/"row_height" as the pointer moves, clamped
     * so the tile never shrinks below 1x1 or grows past the grid's 12
     * columns from its current "column_start". Stops the event from
     * reaching "onTilePointerDown" so resizing never also moves the
     * tile.
     *
     * @param {PointerEvent} ev
     * @param {Number} tileId
     */
    onResizeHandlePointerDown(ev, tileId) {
        if (ev.button !== 0) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        const tile = this.tileById(tileId);
        const startX = ev.clientX;
        const startY = ev.clientY;
        const startWidth = tile.column_width;
        const startHeight = tile.row_height;
        const columnStep = gridColumnStep(this.gridRef.el.getBoundingClientRect().width);
        const rowStep = gridRowStep();
        const target = ev.currentTarget;
        target.setPointerCapture(ev.pointerId);
        const onMove = (moveEv) => {
            const deltaColumns = Math.round((moveEv.clientX - startX) / columnStep);
            const deltaRows = Math.round((moveEv.clientY - startY) / rowStep);
            tile.column_width = clampGrid(
                startWidth + deltaColumns,
                1,
                GRID_COLUMNS - tile.column_start
            );
            tile.row_height = Math.max(1, startHeight + deltaRows);
        };
        const onUp = (upEv) => {
            target.releasePointerCapture(upEv.pointerId);
            target.removeEventListener("pointermove", onMove);
            target.removeEventListener("pointerup", onUp);
        };
        target.addEventListener("pointermove", onMove);
        target.addEventListener("pointerup", onUp);
    }

    onSaveClick() {
        this.props.onSave(
            this.state.layout.map((tile) => ({
                id: tile.id,
                column_start: tile.column_start,
                row_start: tile.row_start,
                column_width: tile.column_width,
                row_height: tile.row_height,
            }))
        );
    }

    onCancelClick() {
        this.props.onCancel();
    }
}
