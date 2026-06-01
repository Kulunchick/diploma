export interface Service {
  id: string;
  name: string;
  description: string | null;
  group_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface ServiceInput {
  name: string;
  description?: string | null;
}
