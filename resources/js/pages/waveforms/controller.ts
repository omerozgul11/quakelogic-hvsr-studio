import type { Step, StepWarning } from '@/api/types';

export interface WaveformController {
    steps: Step[];
    warnings: StepWarning[];
    fs: number | null;
    duration: number | null;
    previewing: boolean;
    autoPreview: boolean;
    onChange: () => void;
    preview: () => Promise<void>;
    run: (name: string) => Promise<void>;
    reset: () => void;
    suggestRunName: () => string;
}
