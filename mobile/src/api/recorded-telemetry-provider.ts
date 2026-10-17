// Replace this adapter with authenticated GET replay requests in Step 3; UI stays unchanged.
import fixtures from '@/demo/recorded/clips.json';
import { validateClip } from '@/lib/recorded-replay';
import type { ReplayClip, ReplayClipMetadata } from '@/types/recorded-telemetry';
export interface RecordedTelemetryProvider {
  listClips(): Promise<ReplayClipMetadata[]>;
  getClip(clipId: string): Promise<ReplayClip>;
}
const clips = fixtures as ReplayClip[];
export const localRecordedProvider: RecordedTelemetryProvider = {
  async listClips() {
    return clips.map(clip => {
      validateClip(clip);
      const { samples, persistent_intervals, ...metadata } = clip;
      void samples; void persistent_intervals;
      return metadata;
    });
  },
  async getClip(id) {
    const clip = clips.find(c => c.clip_id === id);
    if (!clip) throw new Error('Recording not found. Choose another clip.');
    // Each consumer receives its own data; playback never mutates the bundled results.
    return validateClip(JSON.parse(JSON.stringify(clip)) as ReplayClip);
  },
};
