export interface ServiceGroup {
  id: string;
  name: string;
  members: string[];
  created_at: string;
  updated_at: string;
}

export interface ServiceGroupInput {
  name: string;
  member_ids: string[];
}
