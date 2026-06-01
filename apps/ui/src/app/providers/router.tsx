import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'sonner';

import { ROUTES } from '@shared/config/routes';
import Navbar from '@widgets/navbar';
import RequireAuth from '@app/providers/require-auth';
import RedirectIfAuthenticated from '@app/providers/redirect-if-authenticated';

import LoginPage from '@pages/login/ui/LoginPage';
import RegisterPage from '@pages/register/ui/RegisterPage';
import ServicesPage from '@pages/services/ui/ServicesPage';
import ServiceGroupsPage from '@pages/service-groups/ui/ServiceGroupsPage';
import ProvidersPage from '@pages/providers/ui/ProvidersPage';
import PlanningPage from '@pages/planning/ui/PlanningPage';
import FormationsPage from '@pages/formations-list/ui/FormationsPage';
import FormationDetailPage from '@pages/formation-detail/ui/FormationDetailPage';
import FormationsComparePage from '@pages/formations-compare/ui/FormationsComparePage';

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
          Інформаційна система формування пакетів сервісів для провайдерів інфокомунікацій
        </h1>

        <Navbar />

        <Routes>
          <Route path="/" element={<Navigate to={ROUTES.formations} replace />} />

          <Route path={ROUTES.login} element={authPage(<LoginPage />)} />
          <Route path={ROUTES.register} element={authPage(<RegisterPage />)} />

          <Route path={ROUTES.services} element={protect(<ServicesPage />)} />
          <Route path={ROUTES.serviceGroups} element={protect(<ServiceGroupsPage />)} />
          <Route path={ROUTES.providers} element={protect(<ProvidersPage />)} />
          <Route path={ROUTES.planning} element={protect(<PlanningPage />)} />
          <Route path={ROUTES.formations} element={protect(<FormationsPage />)} />
          <Route path={ROUTES.formationsCompare} element={protect(<FormationsComparePage />)} />
          <Route path="/formations/:id" element={protect(<FormationDetailPage />)} />
        </Routes>
      </div>
      <Toaster richColors position="top-right" />
    </Router>
  );
}
