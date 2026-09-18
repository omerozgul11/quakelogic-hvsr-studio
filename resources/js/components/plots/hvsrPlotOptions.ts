export interface HvsrPlotOptions {
    showMean: boolean;
    /** Dispersion as a shaded band, dashed ±σ curves, or hidden. */
    stdMode: 'band' | 'lines' | 'none';
    showT10: boolean;
    showSingle: boolean;
    showLoaded: boolean;
    dbHorizontal: boolean;
    dbVertical: boolean;
    freqLog: boolean;
    freqRange: [number, number] | null;
    ratioRange: [number, number] | null;
    dbRange: [number, number] | null;
    selectWindows: boolean;
}
export const defaultHvsrPlotOptions = (): HvsrPlotOptions => ({ showMean: true, stdMode: 'band', showT10: false, showSingle: false, showLoaded: true, dbHorizontal: false, dbVertical: false, freqLog: true, freqRange: null, ratioRange: null, dbRange: null, selectWindows: false });
