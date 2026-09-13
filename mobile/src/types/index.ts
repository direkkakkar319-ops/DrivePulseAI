export interface TelemetryPayload {
  vehicle_id: string;
  speed_kmph: number;
  engine_rpm: number;
  coolant_temp_c: number;
  battery_voltage: number;
  engine_load_pct: number;
  vibration: number;
  timestamp: string;
  source: 'simulated' | 'real';
}

export interface PredictionResponse {
  vehicle_id: string;
  health_score: number;
  health_score_display: number;
  failure_probability: number;
  rul_estimate: number;
  anomaly_score: number;
  explanation: Record<string, number>;
  contributions: Record<string, number>;
  confidence: number | null;
  timestamp: string;
  source: string;
}
