/** Rainbow palette for analysis windows (blue → green → yellow → red in time order), as in QLExplorer-HVSR. */
export function windowColor(index: number, count: number, alpha = 1): string {
    const n = Math.max(1, count - 1);
    const t = Math.min(1, Math.max(0, index / n));
    const hue = 240 - 240 * t; // 240° (blue) → 0° (red)
    return alpha >= 1 ? `hsl(${hue.toFixed(1)} 85% 45%)` : `hsl(${hue.toFixed(1)} 85% 45% / ${alpha})`;
}

/** Colour for a window item from its `color_index` (falls back to its position). */
export function windowColorFor(w: { color_index?: number; index: number }, count: number, alpha = 1): string {
    return windowColor(w.color_index ?? w.index, count, alpha);
}

/** Plotly "Jet" colour scale (QLExplorer-style heat maps). */
export const JET: [number, string][] = [
    [0, '#000080'], [0.11, '#0000ff'], [0.34, '#00ffff'], [0.5, '#00ff00'], [0.65, '#ffff00'], [0.88, '#ff0000'], [1, '#800000'],
];
