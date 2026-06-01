export interface Provider {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProviderInput {
  name: string;
  description?: string | null;
}
