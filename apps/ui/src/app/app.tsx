import { QueryProvider } from '@app/providers/query';
import { AuthProvider } from '@app/providers/auth';
import { AppRouter } from '@app/providers/router';

export default function App() {
  return (
    <QueryProvider>
      <AuthProvider>
        <AppRouter />
      </AuthProvider>
    </QueryProvider>
  );
}
