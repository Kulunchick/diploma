import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'sonner';

import { ROUTES } from '@shared/config/routes';
import RequireAuth from '@app/providers/require-auth';
import RedirectIfAuthenticated from '@app/providers/redirect-if-authenticated';

// Screens — still at old paths; will be moved to pages/ in step 9.
import Navbar from '@/widgets/navbar';
import Login from '@/screens/Login';
import Register from '@/screens/Register';
import Services from '@/screens/Services';
import ServiceGroups from '@/screens/ServiceGroups';
import Providers from '@/screens/Providers';
import Planning from '@/screens/Planning';
import Formations from '@/screens/Formations';
import FormationDetail from '@/screens/FormationDetail';
import FormationsCompare from '@/screens/FormationsCompare';

function protect(element: React.ReactNode) {
  return <RequireAuth>{element}</RequireAuth>;
}

function authPage(element: React.ReactNode) {
  return <RedirectIfAuthenticated>{element}</RedirectIfAuthenticated>;
}

export function AppRouter() {
  return (
    <Router>
      <div className="p-4">
        <h1 className="text-3xl font-bold text-center mb-8">
          Формування пакетів сервісів для провайдерів інфокомунікацій
        </h1>

        <Navbar />

        <Routes>
          <Route path="/" element={<Navigate to={ROUTES.formations} replace />} />

          <Route path={ROUTES.login} element={authPage(<Login />)} />
          <Route path={ROUTES.register} element={authPage(<Register />)} />

          <Route path={ROUTES.services} element={protect(<Services />)} />
          <Route path={ROUTES.serviceGroups} element={protect(<ServiceGroups />)} />
          <Route path={ROUTES.providers} element={protect(<Providers />)} />
          <Route path={ROUTES.planning} element={protect(<Planning />)} />
          <Route path={ROUTES.formations} element={protect(<Formations />)} />
          <Route path={ROUTES.formationsCompare} element={protect(<FormationsCompare />)} />
          <Route path="/formations/:id" element={protect(<FormationDetail />)} />
        </Routes>
      </div>
      <Toaster richColors position="top-right" />
    </Router>
  );
}
