// Explicit artificial protocol fixtures, not claimed ML predictions.
import { render, screen } from '@testing-library/react-native';
import { LeafTrendResults } from '../src/components/insights/leaf-trend-results';
import { LeafResults } from '../src/components/insights/leaf-analysis-results';
import { parseLeafAnalysis } from '../src/lib/leaf-analysis';
import { parseLeafTrend } from '../src/lib/leaf-trend';
import { sampleResult } from './leaf-fixtures';
import type { TrendAnalysis } from '../src/types/leaf-analysis';

function fixture(): TrendAnalysis {
  return { status: 'completed', reason: null, prepared_readings: 8, analyzed_readings: 8, skipped_readings: 0, observed_days: 8,
    start_timestamp_us:1704067200000000,end_timestamp_us:1704672000000000,source_fields:['Pack_Avg_C_Temp'],
    signal_availability: { pack_avg_temp: { status:'available',reason:null },pack_temp_rise:{status:'unavailable',reason:'Ambient units unverified'} },
    warnings: [],limitations:['Observed daily points are not necessarily consecutive calendar days.'],
    result: { schema_version:1,model_version:'nissan-leaf-rolling-zscore-v1',assessment_type:'rolling_zscore_drift_detection',status:'ok',is_drift_detected:false,drift_alerts_count:0,alerts:[],days_evaluated:8,window_size_days:14,warning_z_threshold:2.5,critical_z_threshold:3.5,
      signal_details:{pack_avg_temp:{status:'normal',label:'Pack average temperature',unit:'°C',current_value:25,baseline_mean:25,baseline_std:.5,z_score:0,consecutive_abnormal_days:0,baseline_window_days:7}} } };
}
it('renders genuine-shaped no-alert status without implying a fault diagnosis',async()=>{
  const data=fixture();expect(parseLeafTrend(data)).toBe(data);
  await render(<LeafTrendResults trend={data}/>);
  expect(screen.getByText('Battery Trend Analysis')).toBeTruthy();
  expect(screen.getByText('No unusual drift detected in the evaluated latest daily signals.')).toBeTruthy();
  expect(screen.getByText('Ambient units unverified')).toBeTruthy();
  expect(screen.getByText(/not a confirmed mechanical fault/)).toBeTruthy();
});
it.each(['warning','critical'] as const)('renders actual %s severity and measured baseline comparisons',async severity=>{
  const data=fixture(), detail=data.result!.signal_details.pack_avg_temp!;
  detail.status=severity;detail.z_score=3.5;detail.consecutive_abnormal_days=2;
  data.result!.is_drift_detected=true;data.result!.drift_alerts_count=1;
  data.result!.alerts=[{signal:'pack_avg_temp',label:detail.label,severity,z_score:3.5,current_value:25,baseline_mean:25,baseline_std:.5,unit:'°C',consecutive_days:2,explanation:'Controlled protocol fixture'}];
  expect(parseLeafTrend(data)).toBe(data);await render(<LeafTrendResults trend={data}/>);
  expect(screen.getByText('Unusual drift detected · 1 alerts')).toBeTruthy();
  expect(screen.getByText(`${severity==='critical'?'Critical':'Warning'} trend alert · Pack average temperature`)).toBeTruthy();
  expect(screen.getByText('Controlled protocol fixture')).toBeTruthy();
  expect(screen.getByText(/Measured daily value: 25 °C/)).toBeTruthy();
});
it('renders insufficient history without treating absence of alerts as a normal finding',async()=>{
  const data=fixture();data.status='insufficient_history';data.reason='At least 8 observed UTC days are required; 1 available.';data.observed_days=1;
  data.result={schema_version:1,model_version:'nissan-leaf-rolling-zscore-v1',assessment_type:'rolling_zscore_drift_detection',status:'insufficient_history',days_available:1,min_days_required:8,is_drift_detected:false,drift_alerts_count:0,alerts:[],signal_details:{}};
  expect(parseLeafTrend(data)).toBe(data);await render(<LeafTrendResults trend={data}/>);
  expect(screen.getByText(data.reason)).toBeTruthy();expect(screen.queryByText(/No unusual drift detected/)).toBeNull();
});
it('handles older responses without trend while leaving point-anomaly charts intact',async()=>{
  const data=sampleResult();expect(parseLeafAnalysis(data)).toBe(data);
  await render(<LeafResults data={data}/>);expect(screen.getByTestId('Anomaly score chart')).toBeTruthy();
  expect(screen.getByText('Trend analysis is unavailable from this backend response.')).toBeTruthy();
});
it.each(['failed','unavailable'] as const)('renders %s independent capability',async status=>{
  const data=fixture();data.status=status;data.result=null;data.reason='Trend service unavailable';data.analyzed_readings=0;
  expect(parseLeafTrend(data)).toBe(data);await render(<LeafTrendResults trend={data}/>);
  expect(screen.getByText(data.reason)).toBeTruthy();expect(screen.queryByText(/No unusual drift detected/)).toBeNull();
});
it.each(['count','identity','nonfinite','coverage','threshold','missing_measurement','false_normal','unknown_signal','partial_result'])('rejects malformed trend data: %s',failure=>{
  const data=fixture();
  if(failure==='count')data.result!.drift_alerts_count=1;
  if(failure==='identity')data.result!.model_version='wrong' as 'nissan-leaf-rolling-zscore-v1';
  if(failure==='nonfinite')data.result!.signal_details.pack_avg_temp!.z_score=Infinity;
  if(failure==='coverage')data.result!.days_evaluated=9;
  if(failure==='threshold')data.result!.critical_z_threshold=1;
  if(failure==='missing_measurement')delete data.result!.signal_details.pack_avg_temp!.baseline_std;
  if(failure==='false_normal')data.result!.signal_details.pack_avg_temp!.status='warning';
  if(failure==='unknown_signal')(data.result!.signal_details as Record<string,unknown>).unknown={status:'normal'};
  if(failure==='partial_result'){data.status='failed';data.result!.is_drift_detected=false;}
  expect(()=>parseLeafTrend(data)).toThrow();
});
it('rejects mismatched recording and trend reading counts in unified results',()=>{
  const data=sampleResult();data.trend=fixture();expect(()=>parseLeafAnalysis(data)).toThrow();
});

it('does not describe an empty collection of assessed signals as a completed no-alert analysis', () => {
  const data=fixture(); data.result!.signal_details={}; expect(()=>parseLeafTrend(data)).toThrow();
});
