/** Primitive user type used by shared/zustand/useAuthStore.
 *  entities/user re-exports this as its canonical User type. */
export interface User {
  id: string;
  email: string;
  full_name: string | null;
  created_at: string;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
}

export interface RegisterResponse {
  user: User;
  access_token: string;
  token_type: string;
}
