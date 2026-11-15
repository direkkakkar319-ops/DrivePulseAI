// Metadata-only selection UI; no picker dependency, upload endpoint, file parsing, or inference.
import { StyleSheet, View } from 'react-native';
import { AppButton } from '@/components/ui/app-button';
import { AppIcon } from '@/components/ui/app-icon';
import { AppStatus } from '@/components/ui/app-status';
import { AppText } from '@/components/ui/app-text';
import type { CsvFileMetadata } from '@/types/ai-insights';
import { colors, radii, spacing } from '@/theme/tokens';

interface CsvSourceControlProps {
  available: boolean;
  selecting: boolean;
  file?: CsvFileMetadata;
  error?: string;
  onSelect: () => void;
  onClear: () => void;
}
export function CsvSourceControl({ available, selecting, file, error, onSelect, onClear }: CsvSourceControlProps) {
  return <View style={styles.control}>
    <AppIcon name="plus" color={colors.accent} />
    <AppText variant="subtitle">Upload CSV Dataset</AppText>
    <AppText tone="secondary">{available ? 'Select a CSV file. Selection does not upload or analyse it.'
      : 'CSV selection and upload are not yet available in this build.'}</AppText>
    {file && <View style={styles.file} accessibilityLiveRegion="polite">
      <AppStatus label="Selected CSV · Not uploaded" tone="info" />
      <AppText variant="label">{file.name}</AppText>
      {file.sizeBytes !== undefined && <AppText variant="caption" tone="secondary">{file.sizeBytes.toLocaleString()} bytes</AppText>}
      {!!file.mimeType && <AppText variant="caption" tone="secondary">{file.mimeType}</AppText>}
      <AppButton title="Remove CSV selection" variant="text" disabled={selecting} onPress={onClear} />
    </View>}
    <AppButton title={file ? 'Replace CSV file' : 'Select CSV file'} variant="secondary"
      disabled={!available} loading={selecting} onPress={onSelect} />
    {!!error && <AppStatus label="Could not select CSV" description={error} tone="error" variant="notice" />}
  </View>;
}
const styles = StyleSheet.create({
  control: { padding: spacing.md, gap: spacing.sm, borderWidth: 1, borderStyle: 'dashed',
    borderColor: colors.borderStrong, borderRadius: radii.md, backgroundColor: colors.backgroundSecondary },
  file: { gap: spacing.xs },
});
