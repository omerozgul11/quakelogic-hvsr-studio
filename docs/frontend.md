# Frontend (Vue 3 + TypeScript + Tailwind 4 + Plotly)

Entry points: `resources/js/app.ts` and `resources/css/app.css`, injected by Laravel's `@vite`
directive into `resources/views/app.blade.php` (mount point `#app`). Everything is bundled by
`npm run build` into `public/build` — fonts (Inter, JetBrains Mono via `@fontsource-variable`),
icons (`lucide-vue-next`), and `plotly.js-cartesian-dist-min`. No CDN or network access.

```
resources/js/
  app.ts                Vue app, Pinia, router, theme bootstrap
  App.vue               renders layout/AppShell.vue
  router.ts             history-mode routes (see below)
  shims.d.ts            .vue + plotly module typings
  api/
    types.ts            every JSON shape of docs/architecture.md (Laravel + engine)
    client.ts           fetch wrapper → ApiError{status,message,errors,payload}; downloadFile()
    index.ts            typed endpoint map (api.projects.*, api.recordings.*, api.analyses.* …)
  stores/
    app.ts              theme (light|dark|system, localStorage 'hvsr-theme'), /api/app/status polling, settings
    project.ts          project list, current project tree (stations → recordings → runs/analyses), deep-link helpers
    jobs.ts             generic job tracker (1 s polling of any poll() fn, cancel/onDone hooks) → JobStrip
    toast.ts            notifications
  composables/
    useResizable.ts     pointer-event splitters (min/max, localStorage persistence)
    usePanel.ts         provide/inject host for the right-hand Processing Panel
  layout/               AppShell (top bar, navigator, workspace, processing panel), JobStrip, Toasts
  components/ui/        Button, Panel, Field, NumberInput, Select, Toggle, Modal, Tabs, Badge, StatusDot,
                        Dropdown/MenuItem, ProgressBar, EmptyState, ErrorBanner
  components/plots/     PlotlyChart (wrapper) + WaveformPlot, SpectraPlot, SpectrogramPlot, HvsrPlot,
                        WindowsPlot, AzimuthHeatmap, PeakDistributionPlot, ComparePlot, FilterResponsePlot
  components/processing/ defaults.ts (step catalogue + HVSR defaults + client-side validation),
                        StepList.vue / StepEditor.vue (toolbox), HvsrParamsForm.vue
  pages/                Projects, ProjectOverview, ImportWizard, Waveforms (+ waveforms/*), WindowSelection,
                        HvsrAnalysis (+ hvsr/*), BatchCompare, Reports, Settings
  utils/                format.ts (numbers/durations/bytes), plotTheme.ts (brand colours, Plotly templates)
```

## Routes

| Path | Page |
|---|---|
| `/projects` | project list, create/rename/delete |
| `/projects/:p` | overview: stations (inline edit), recordings, recent analyses |
| `/projects/:p/import` | 4-step import wizard |
| `/recordings/:r/waveforms` | synchronized 3-C plots, toolbox panel, spectra tabs, runs |
| `/recordings/:r/windows` | window screening, manual accept/reject, table |
| `/recordings/:r/hvsr` | new analysis (parameter panel) |
| `/analyses/:a` | results view for an analysis (and re-run panel) |
| `/projects/:p/compare` | batch runner + curve comparison |
| `/projects/:p/reports` | reports and export bundles |
| `/settings` | theme, defaults, engine health, version |

## How state flows

* Pages load their subject through the project store (`ensureForRecording` / `ensureForAnalysis`
  fetch the owning project tree so deep links work after a reload).
* Long engine jobs (processing runs, analyses, reports, batches) are tracked in the jobs store.
  Each tracked job supplies its own `poll()` (usually the owning Laravel resource) and an `onDone`
  callback; `JobStrip` shows progress and Cancel buttons globally.
* Pages that need the right-hand Processing Panel build a reactive **controller** object
  (`waveforms/controller.ts`, `hvsr/WindowsPanel.vue`, `hvsr/HvsrPanel.vue`) and register a
  component + props with `useProcessingPanel()`. The panel host (AppShell) renders it; the page is
  unmounted → the panel clears itself.
* Window selection → HVSR: parameters, overrides and the chosen run are carried through
  `sessionStorage` (`hvsr/draft.ts`) so the two pages stay in sync.
* Waveform plots request server-side min/max downsampling for the visible range
  (`GET /api/recordings/{r}/data?t_start&t_end&max_points`) on every Plotly `relayout`; a note states
  when the display is reduced. Analyses always run on the full-resolution data in the engine.

## Adding a plot

1. Create `components/plots/MyPlot.vue`, build `data: Data[]` and `layout: Partial<Layout>` as
   computed values and render `<PlotlyChart :data :layout :height :title export-name="…" />`.
2. Always set axis titles with units, a `hovertemplate`, and `type: 'log'` where frequency is on an axis.
3. Theme colours come from `utils/plotTheme.ts`; `PlotlyChart` merges the light/dark base layout and
   redraws on theme change and container resize. Use `extra-exports` to add engine-side PDF/PNG/SVG
   exports (`/api/analyses/{a}/figure`).

## Build

```
npm install
npm run build          # writes public/build (+ manifest) consumed by Laravel
npm run typecheck      # vue-tsc --noEmit
```

## Navigation model (current design)

* `components/PageHeader.vue` + `composables/useNavigation.ts`: every page shows a breadcrumb
  (Projects › project › recording › analysis) and a "‹ Back" button that goes to the hierarchical
  parent (not browser history). Recording pages carry a `StepSwitcher` (1 Waveforms · 2 Windows ·
  3 HVSR) that preserves the selected processing run through the `?run=` query.
* `layout/Navigator.vue`: grouped menu (Workspace / Analysis / Results; User manual and Settings
  pinned at the bottom) and a recording-centred tree — one row per recording under a station
  caption; the active recording auto-expands to show "Analyses (n)" and a collapsed
  "Processing runs (n)"; hover quick actions, filter box above six recordings, keyboard Up/Down/Enter.
* `components/ui/Tabs.vue` is a segmented control; `Toggle` is an iOS-style switch; cards use the
  `card` utility with dividers. Guided workflow: `stores/guide.ts` + `components/GuideWizard.vue`;
  in-app docs: `pages/Manual.vue` (`GET /api/docs/{doc}` rendered with `marked`).

## GeoExplorer-parity views (2026-09-16)

* `utils/windowPalette.ts` — rainbow palette (blue→red in time order, `color_index`) shared by the
  waveform/window overlays, window tables and single-window H/V curves; `JET` colour scale for heat maps.
* Windows page (`pages/WindowSelection.vue`, `pages/hvsr/WindowsPanel.vue`, `components/processing/HvsrParamsForm.vue`):
  window modes Fixed / Automatic (variable length, min–max) / Custom (`params.windows`, legacy
  `window_length_s`/`overlap` kept in sync by `syncWindowAliases`), amplitude levels, free selection
  (box drag → custom window), editable start/end and delete in custom mode, Select all / Invert / Clear,
  Hide selected windows, common amplitude scale, T10, Save/Load window set (JSON; `POST /recordings/{r}/windows/import`),
  bookmarks (localStorage `hvsr-bookmarks:<rid>`) + "Reject bookmarked windows".
* `components/SeismogramPlayer.vue` — sonification with the Web Audio API: samples from
  `GET /recordings/{r}/samples` are re-clocked at the playback frequency (linear interpolation to the
  audio-context rate), play/pause/rewind/forward/stop, volume, moving cursor (emits `time`), Bookmark (key B).
* Results page (`pages/HvsrAnalysis.vue`): window table (colour, #, length, Use) with Select all/Invert/Clear
  and "Re-run with these windows" (creates a new analysis with the edited overrides); `HvsrPlot` options
  (`components/plots/hvsrPlotOptions.ts`): show ratio, σ band/curves/off, T10 shading, coloured single ratios,
  box selection of windows (`selectWindows` event), loaded curves (`POST /projects/{p}/curves`), H/V dB
  spectra on a right axis, manual scales, log/linear frequency; `pages/hvsr/SesameBoxes.vue` (Curve I–III,
  Peak I–VI, Overall); tabs H/V vs time (`components/plots/HvTimePlot.vue`, from `result.time_frequency`)
  and H/V rotate (`AzimuthHeatmap.vue`, jet colours, max-colour %); Modelling (`pages/hvsr/ModellingTab.vue`,
  `ModelPlot.vue`, `ProfilePlot.vue`; `POST /engine/model-hvsr`, saved models via `PUT /analyses/{a}/models`).
* `components/SurveyDialog.vue` — report details (survey, place, photos, notes; `PUT /analyses/{a}/survey`)
  used from the analysis page and the Reports page before generating the PDF.
* Compare page: "Load curve from file" (.hv/.csv) overlays external curves; Projects page: Backup (zip) and
  Restore from backup; import wizard accepts SAF (`inspect.format === 'saf'`, no mapping) and any
  ObsPy-readable trace file (`'seismic'`, handled like MiniSEED).
