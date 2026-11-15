// Fixed illustrative UI fixtures, unrelated to training data, recordings, or saved vehicles.
import type { AnalysisResult, SampleTelemetry } from '@/types/ai-insights';

export const demoInsights = {
  source: 'simulated',
  description: 'Illustrative UI samples only. Not from a vehicle or a trained model.',
  results: [
    { id: 'battery', title: 'Battery Health', value: '94.2%', sourceLabel: 'Demo',
      explanation: 'Illustrative battery health value; no battery assessment was performed.' },
    { id: 'anomaly', title: 'Anomaly Detection', value: 'Normal', sourceLabel: 'Demo',
      explanation: 'Sample anomaly status; no anomaly detector was run.' },
    { id: 'fault', title: 'Fault Detection', value: 'None', sourceLabel: 'Demo',
      explanation: 'Sample fault status; no diagnostic scan was performed.' },
    { id: 'maintenance', title: 'Predictive Maintenance', value: 'Low', sourceLabel: 'Demo',
      explanation: 'Illustrative maintenance risk; no maintenance prediction was calculated.' },
  ] satisfies readonly AnalysisResult[],
  telemetry: [
    { id: 'voltage', label: 'Battery Voltage', value: 360, unit: 'V', source: 'simulated' },
    { id: 'current', label: 'Battery Current', value: 42, unit: 'A', source: 'simulated' },
    { id: 'temperature', label: 'Battery Temperature', value: 29, unit: '°C', source: 'simulated' },
    { id: 'speed', label: 'Vehicle Speed', value: 64, unit: 'km/h', source: 'simulated' },
    { id: 'charge', label: 'State of Charge', value: 78, unit: '%', source: 'simulated' },
  ] satisfies readonly SampleTelemetry[],
} as const;
