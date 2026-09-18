declare module '*.vue' {
    import type { DefineComponent } from 'vue';
    const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>;
    export default component;
}

declare module 'plotly.js-cartesian-dist-min' {
    import * as Plotly from 'plotly.js';
    export = Plotly;
}
