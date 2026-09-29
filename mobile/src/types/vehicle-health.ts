// Frontend view models; these are not finalized backend wire contracts.
import type { TelemetryPayload } from './index';
export type SensorKey = Exclude<keyof TelemetryPayload, 'vehicle_id' | 'timestamp' | 'source'>;
export type DataSource = 'simulated' | 'real' | 'none';
export type Scenario =
  | 'voltage'
  | 'normal'
  | 'temperature'
  | 'vibration'
  | 'no-data'
  | 'waiting'
  | 'collecting'
  | 'assessment-unavailable'
  | 'missing'
  | 'stale'
  | 'disconnected'
  | 'failed'
  | 'loading';
export interface VehicleDraft {
  name: string;
  make: string;
  model: string;
  year: string;
  notes: string;
}
export interface Vehicle extends VehicleDraft {
  id: string;
  source: DataSource;
}
export interface Reading {
  timestamp: string;
  values: Record<SensorKey, number | null>;
}
export interface Insight {
  id: string;
  vehicleId: string;
  title: string;
  sensor: SensorKey;
  observed: number;
  timestamp: string;
  explanation: string;
  nextStep: string;
  source: DataSource;
}
export interface Assessment {
  score: number;
  label: string;
  explanation: string;
  timestamp: string;
  source: DataSource;
}
export interface ReportPreview {
  id: string;
  vehicleId: string;
  createdAt: string;
  start: string;
  end: string;
  source: DataSource;
  assessment: Assessment | null;
  observations: Insight[];
}
export interface VehicleSnapshot {
  vehicleId: string;
  source: DataSource;
  connection: 'playback' | 'connected' | 'waiting' | 'disconnected' | 'none';
  freshness: 'current' | 'stale' | 'unavailable';
  assessmentState: 'available' | 'collecting' | 'unavailable';
  latest: Reading | null;
  history: Reading[];
  assessment: Assessment | null;
  insights: Insight[];
  report: ReportPreview | null;
}
export type Resource<T> =
  { status: 'loading' } | { status: 'error'; message: string } | { status: 'ready'; data: T };
