import { http, qs, downloadFile } from './client';
import type {
    Analysis, AppStatus, Batch, CompareEntry, CreateAnalysisRequest, CreateRecordingRequest, DisplayData,
    ExportKind, FigureKind, FilterResponse, HvsrParams, Job, Preset, PreviewResult, ProcessingRun, Project,
    Recording, Settings, SpectraParams, SpectraResult, Station, Step, Upload, WindowCurves, WindowOverrides,
    WindowsResult, ActivityEntry, Ulid, DocInfo, ModelRequest, ModelResponse, GroundModel, ImportedCurve, Survey, WindowSetExport, WindowImportResult, SamplesResponse,
} from './types';

export const api = {
    docs: {
        list: () => http.get<DocInfo[]>('/docs'),
        get: async (key: string): Promise<string> => {
            const res = await fetch(`/api/docs/${key}`, { headers: { Accept: 'text/markdown' } });
            if (!res.ok) throw new Error(res.status === 404 ? 'This document is not included in the installation.' : `Could not load the document (HTTP ${res.status}).`);
            return res.text();
        },
    },
    app: {
        status: () => http.get<AppStatus>('/app/status'),
        settings: () => http.get<Settings>('/settings'),
        saveSettings: (s: Partial<Settings>) => http.put<Settings>('/settings', s),
        job: (id: string) => http.get<Job>(`/jobs/${id}`),
        filterResponse: (fs: number, step: Step, n_points = 1024) =>
            http.post<FilterResponse>('/engine/filter-response', { fs, step, n_points }),
        modelHvsr: (req: ModelRequest) => http.post<ModelResponse>('/engine/model-hvsr', req),
    },
    projects: {
        list: () => http.get<Project[]>('/projects'),
        get: (id: Ulid) => http.get<Project>(`/projects/${id}`),
        create: (data: { name: string; description?: string }) => http.post<Project>('/projects', data),
        update: (id: Ulid, data: Partial<Project>) => http.put<Project>(`/projects/${id}`, data),
        remove: (id: Ulid) => http.delete<void>(`/projects/${id}`),
        history: (id: Ulid) => http.get<ActivityEntry[]>(`/projects/${id}/history`),
        upload: (id: Ulid, files: File[]) => {
            const fd = new FormData();
            for (const f of files) fd.append('files[]', f, f.name);
            return http.post<Upload[]>(`/projects/${id}/uploads`, fd);
        },
        createRecording: (id: Ulid, data: CreateRecordingRequest) => http.post<Recording>(`/projects/${id}/recordings`, data),
        presets: (id: Ulid) => http.get<Preset[]>(`/projects/${id}/presets`),
        createPreset: (id: Ulid, data: { name: string; description?: string; steps: Step[]; hvsr_params: HvsrParams }) =>
            http.post<Preset>(`/projects/${id}/presets`, data),
        createBatch: (id: Ulid, data: { name: string; preset_id: Ulid | null; recording_ids: Ulid[]; run_steps: boolean }) =>
            http.post<Batch>(`/projects/${id}/batches`, data),
        compare: (id: Ulid, analysis_ids: Ulid[]) => http.post<CompareEntry[]>(`/projects/${id}/compare`, { analysis_ids }),
        importCurve: (id: Ulid, file: File) => { const fd = new FormData(); fd.append('file', file, file.name); return http.post<ImportedCurve>(`/projects/${id}/curves`, fd); },
        backup: (id: Ulid) => downloadFile(`/projects/${id}/backup`),
        restore: (file: File) => { const fd = new FormData(); fd.append('file', file, file.name); return http.post<Project>('/projects/restore', fd); },
    },
    stations: {
        create: (projectId: Ulid, data: Partial<Station>) => http.post<Station>(`/projects/${projectId}/stations`, data),
        update: (id: Ulid, data: Partial<Station>) => http.put<Station>(`/stations/${id}`, data),
        remove: (id: Ulid) => http.delete<void>(`/stations/${id}`),
    },
    presets: {
        update: (id: Ulid, data: Partial<Preset>) => http.put<Preset>(`/presets/${id}`, data),
        remove: (id: Ulid) => http.delete<void>(`/presets/${id}`),
    },
    recordings: {
        get: (id: Ulid) => http.get<Recording>(`/recordings/${id}`),
        update: (id: Ulid, data: Partial<Recording>) => http.put<Recording>(`/recordings/${id}`, data),
        remove: (id: Ulid) => http.delete<void>(`/recordings/${id}`),
        data: (id: Ulid, p: { run?: Ulid | null; t_start?: number | null; t_end?: number | null; max_points?: number }) =>
            http.get<DisplayData>(`/recordings/${id}/data${qs(p)}`),
        spectra: (id: Ulid, params: SpectraParams) => http.post<SpectraResult>(`/recordings/${id}/spectra`, params),
        preview: (id: Ulid, body: { steps: Step[]; t_start?: number | null; t_end?: number | null; max_points?: number; run_id?: Ulid | null }) =>
            http.post<PreviewResult>(`/recordings/${id}/processing/preview`, body),
        createRun: (id: Ulid, body: { name: string; steps: Step[] }) => http.post<{ run: ProcessingRun; job: Job | null }>(`/recordings/${id}/runs`, body),
        windows: (id: Ulid, body: { run_id: Ulid | null; params: HvsrParams; window_overrides: WindowOverrides }) =>
            http.post<WindowsResult>(`/recordings/${id}/windows`, body),
        createAnalysis: (id: Ulid, body: CreateAnalysisRequest) => http.post<Analysis>(`/recordings/${id}/analyses`, body),
        samples: (id: Ulid, p: { component: 'n' | 'e' | 'z'; run?: Ulid | null; t_start?: number | null; t_end?: number | null }) =>
            http.get<SamplesResponse>(`/recordings/${id}/samples${qs(p)}`),
        importWindows: (id: Ulid, body: WindowSetExport) => http.post<WindowImportResult>(`/recordings/${id}/windows/import`, body),
    },
    runs: {
        get: (id: Ulid) => http.get<ProcessingRun>(`/runs/${id}`),
        remove: (id: Ulid) => http.delete<void>(`/runs/${id}`),
    },
    analyses: {
        get: (id: Ulid, includeResult = true) => http.get<Analysis>(`/analyses/${id}${qs({ include: includeResult ? 'result' : 'none' })}`),
        update: (id: Ulid, data: Partial<Analysis>) => http.put<Analysis>(`/analyses/${id}`, data),
        remove: (id: Ulid) => http.delete<void>(`/analyses/${id}`),
        windowCurves: (id: Ulid) => http.get<WindowCurves>(`/analyses/${id}/window-curves`),
        rerun: (id: Ulid) => http.post<Analysis>(`/analyses/${id}/rerun`),
        selectPeak: (id: Ulid, frequency: number | null) => http.post<Analysis>(`/analyses/${id}/select-peak`, { frequency }),
        exportUrl: (id: Ulid, kind: ExportKind) => `/analyses/${id}/exports/${kind}`,
        download: (id: Ulid, kind: ExportKind) => downloadFile(`/analyses/${id}/exports/${kind}`),
        figure: (id: Ulid, figure: FigureKind, format: 'png' | 'svg' | 'pdf') =>
            downloadFile(`/analyses/${id}/figure${qs({ figure, format })}`),
        requestReport: (id: Ulid) => http.post<{ job: Job | null; analysis?: Analysis }>(`/analyses/${id}/report`),
        downloadReport: (id: Ulid) => downloadFile(`/analyses/${id}/report`),
        getSurvey: (id: Ulid) => http.get<Survey>(`/analyses/${id}/survey`),
        saveSurvey: (id: Ulid, fd: FormData) => { fd.append('_method', 'PUT'); return http.post<Survey>(`/analyses/${id}/survey`, fd); },
        saveModels: (id: Ulid, models: GroundModel[]) => http.put<{ models: GroundModel[] }>(`/analyses/${id}/models`, { models }),
        windowSet: (id: Ulid) => http.get<WindowSetExport>(`/analyses/${id}/exports/windows-json`),
    },
    batches: {
        get: (id: Ulid) => http.get<Batch>(`/batches/${id}`),
        cancel: (id: Ulid) => http.post<Batch>(`/batches/${id}/cancel`),
    },
};
