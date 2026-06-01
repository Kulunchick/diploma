import { exportCsv, exportJson } from '@entities/formation/api';

export function useExport(id: string) {
  return {
    exportJson: () => exportJson(id),
    exportCsv: () => exportCsv(id),
  };
}
