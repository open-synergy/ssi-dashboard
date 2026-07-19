/**
 * Grid layout constants shared between the read-only dashboard grid
 * (dashboard_action.esm.js/.scss, dashboard_item.esm.js) and the
 * drag-and-resize layout editor (dashboard_layout_editor.esm.js/.scss).
 * Keep these in sync with the ".o_ssi_dashboard_grid" CSS rule in
 * dashboard_action.scss — they describe the very same grid, just with
 * editing affordances on top in the editor.
 */

/** Number of columns the dashboard grid is divided into. */
export const GRID_COLUMNS = 12;
/** Height, in pixels, of a single grid row ("grid-auto-rows" in CSS). */
export const GRID_ROW_HEIGHT = 96;
/** Gap, in pixels, between grid columns/rows ("gap" in CSS). */
export const GRID_GAP = 16;

/**
 * Pixel width of one grid column *step* (the column's own track plus one
 * gap), derived from the grid container's current pixel width. Used to
 * convert a horizontal pointer-drag distance, in pixels, into a number
 * of columns.
 *
 * @param {Number} containerWidth pixel width of the grid container
 *  (its "getBoundingClientRect().width").
 * @returns {Number}
 */
export function gridColumnStep(containerWidth) {
    return (containerWidth - GRID_GAP * (GRID_COLUMNS - 1)) / GRID_COLUMNS + GRID_GAP;
}

/**
 * Pixel height of one grid row *step* (the row's own track plus one
 * gap). Used to convert a vertical pointer-drag distance, in pixels,
 * into a number of rows. Unlike "gridColumnStep", this does not depend
 * on the container's size since every row has the fixed height
 * "GRID_ROW_HEIGHT".
 *
 * @returns {Number}
 */
export function gridRowStep() {
    return GRID_ROW_HEIGHT + GRID_GAP;
}

/**
 * Clamps "value" between "min" and "max" (inclusive).
 *
 * @param {Number} value
 * @param {Number} min
 * @param {Number} max
 * @returns {Number}
 */
export function clampGrid(value, min, max) {
    return Math.min(Math.max(value, min), max);
}
