import { create } from 'zustand';

/** Cross-route transient UI flags. Keep minimal — page-local flags stay in useState. */
interface UiState {
  // Placeholder: add cross-route flags here as needed.
  _placeholder: null;
}

export const useUiStore = create<UiState>()(() => ({
  _placeholder: null,
}));
