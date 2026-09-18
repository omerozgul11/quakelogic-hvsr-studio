import { computed, ref, watch } from 'vue';
import { defineStore } from 'pinia';
import { useProjectStore } from './project';

export interface GuideStep {
    key: string;
    title: string;
    summary: string;
    tips: string[];
    /** Where the "Open this step" button goes; null when it needs something that does not exist yet. */
    route: string | null;
    routeLabel: string;
    /** What the button needs before it becomes available. */
    blocked: string | null;
    done: boolean;
    optional: boolean;
    docAnchor: string;
}

const DISMISS_KEY = 'hvsr-guide-dismissed';
const STEP_KEY = 'hvsr-guide-step';

function readLocal(key: string): string | null {
    try { return localStorage.getItem(key); } catch { return null; }
}
function writeLocal(key: string, value: string | null) {
    try { value === null ? localStorage.removeItem(key) : localStorage.setItem(key, value); } catch { /* private mode */ }
}

export const useGuideStore = defineStore('guide', () => {
    const project = useProjectStore();
    const open = ref(false);
    const step = ref(Number(readLocal(STEP_KEY) ?? 0) || 0);
    const dismissed = ref(readLocal(DISMISS_KEY) === '1');

    const steps = computed<GuideStep[]>(() => {
        const p = project.current;
        const pid = p?.id ?? null;
        const recs = project.recordings;
        const firstRec = recs[0] ?? null;
        const doneAnalyses = project.analyses.filter((a) => a.status === 'done');
        const withPeak = doneAnalyses.find((a) => a.summary?.f0 != null) ?? doneAnalyses[0] ?? null;
        const reported = project.analyses.some((a) => a.report_status === 'done' || (a as { report_ready?: boolean }).report_ready);
        return [
            {
                key: 'project', title: 'Create or open a project',
                summary: 'A project is a folder that keeps stations, recordings, processing runs, analyses and exports together.',
                tips: ['Use one project per survey or site campaign.', 'Everything is stored under the data directory shown in Settings; back up that folder.'],
                route: '/projects', routeLabel: pid ? 'Open the projects list' : 'Go to Projects', blocked: null, done: !!pid, optional: false, docAnchor: '4-projects',
            },
            {
                key: 'import', title: 'Import and validate recordings',
                summary: 'Drop TXT/CSV or MiniSEED files, map the N, E and Z components explicitly, give timing and units, then validate.',
                tips: ['Three separate component files are supported; choose one file per component.', 'When a file has no time column you must enter the sampling rate — nothing is guessed.', 'Errors (gaps, NaNs, misalignment, constant channels) block the import and are explained; warnings are stored with the recording.'],
                route: pid ? `/projects/${pid}/import` : null, routeLabel: 'Open the import wizard', blocked: pid ? null : 'Create or open a project first.', done: recs.length > 0, optional: false, docAnchor: '5-import-and-validation',
            },
            {
                key: 'waveforms', title: 'Inspect waveforms and preprocess',
                summary: 'Look at the three components, spectra and spectrograms. Add processing steps only if the data need them, preview, then "Run & save" a processing run.',
                tips: ['Typical chain: mean removal → linear detrend → band-pass (zero-phase) → taper.', 'The filter response is drawn when a filter step is selected; warnings flag cutoffs near Nyquist and over-processing.', 'Raw data can be analysed directly — this step is optional.'],
                route: firstRec ? `/recordings/${firstRec.id}/waveforms` : null, routeLabel: 'Open waveforms', blocked: firstRec ? null : 'Import a recording first.', done: project.runs.length > 0, optional: true, docAnchor: '6-waveforms-and-preprocessing',
            },
            {
                key: 'windows', title: 'Select analysis windows',
                summary: 'Choose window length and overlap, screen transients with STA/LTA, and accept or reject windows by hand.',
                tips: ['Frequency resolution is 1/T: 60 s windows resolve 0.017 Hz; longer windows for low-frequency sites.', 'Click a window in the plot to toggle it; overrides are kept with the analysis.', 'Aim for at least 10 accepted windows; SESAME also asks for f0 × T × N > 200.'],
                route: firstRec ? `/recordings/${firstRec.id}/windows` : null, routeLabel: 'Open window selection', blocked: firstRec ? null : 'Import a recording first.', done: project.analyses.length > 0, optional: false, docAnchor: '7-window-selection',
            },
            {
                key: 'hvsr', title: 'Run the HVSR analysis',
                summary: 'Set smoothing, frequency range, horizontal combination and statistic, then run. Every parameter and the random seed are stored.',
                tips: ['Konno–Ohmachi b = 40 is the common default; smaller b smooths more.', 'Geometric mean of |N| and |E| is the default horizontal; RMS and directional ratios are available.', 'Dispersion bands describe the scatter of window curves — they are not confidence intervals.'],
                route: firstRec ? `/recordings/${firstRec.id}/hvsr` : null, routeLabel: 'Open HVSR analysis', blocked: firstRec ? null : 'Import a recording first.', done: doneAnalyses.length > 0, optional: false, docAnchor: '8-hvsr-analysis',
            },
            {
                key: 'review', title: 'Review peaks and SESAME criteria',
                summary: 'Check the candidate peaks, the window-level f0 spread, the bootstrap interval and each SESAME criterion; select a peak manually if needed.',
                tips: ['"Multiple peaks" and "no clear peak" are explicit outcomes, not failures.', 'The H/V amplitude is a spectral ratio, not site amplification.', 'Use the azimuthal tab to look for directional effects.'],
                route: withPeak ? `/analyses/${withPeak.id}` : null, routeLabel: 'Open the latest analysis', blocked: withPeak ? null : 'Run an analysis first.', done: !!withPeak?.summary?.f0, optional: false, docAnchor: '8-hvsr-analysis',
            },
            {
                key: 'report', title: 'Export results and the PDF report',
                summary: 'Download CSV/JSON exports, figures and the PDF report with metadata, settings, window statistics, peaks, SESAME table and limitations.',
                tips: ['The configuration JSON reproduces the analysis; "Re-run" repeats it with the stored seed.', 'All exports are written into the analysis folder and work offline.'],
                route: pid ? `/projects/${pid}/reports` : null, routeLabel: 'Open reports & exports', blocked: pid ? null : 'Create or open a project first.', done: reported, optional: false, docAnchor: '10-reports-and-exports',
            },
            {
                key: 'batch', title: 'Batch processing and comparison',
                summary: 'Apply a saved preset to many recordings and overlay the resulting curves across stations or processing runs.',
                tips: ['Save the toolbox steps and HVSR parameters as a preset first.', 'A failed file is recorded and skipped; the rest of the batch continues.'],
                route: pid ? `/projects/${pid}/compare` : null, routeLabel: 'Open batch comparison', blocked: pid ? null : 'Create or open a project first.', done: false, optional: true, docAnchor: '9-batch-processing-and-comparison',
            },
        ];
    });

    const current = computed(() => steps.value[Math.min(step.value, steps.value.length - 1)]!);
    const completed = computed(() => steps.value.filter((s) => s.done).length);
    const nextIncomplete = computed(() => steps.value.findIndex((s) => !s.done && !s.optional));

    function show(atStep?: number) {
        if (atStep !== undefined) step.value = atStep;
        else if (nextIncomplete.value >= 0 && !readLocal(STEP_KEY)) step.value = nextIncomplete.value;
        open.value = true;
    }
    function hide() { open.value = false; }
    function next() { if (step.value < steps.value.length - 1) step.value += 1; }
    function back() { if (step.value > 0) step.value -= 1; }
    function goTo(i: number) { step.value = i; }
    function dismiss(value: boolean) { dismissed.value = value; writeLocal(DISMISS_KEY, value ? '1' : null); }
    /** Called once at start-up: open automatically the first time the application is used. */
    function autoOpen() { if (!dismissed.value && readLocal(STEP_KEY) === null) open.value = true; }

    watch(step, (v) => writeLocal(STEP_KEY, String(v)));

    return { open, step, steps, current, completed, nextIncomplete, dismissed, show, hide, next, back, goTo, dismiss, autoOpen };
});
