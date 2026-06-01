import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'sonner'

import Navbar from './widgets/navbar'
import { AuthProvider } from './auth/AuthContext.tsx'
import RequireAuth from './auth/RequireAuth.tsx'
import RedirectIfAuthenticated from './auth/RedirectIfAuthenticated.tsx'
import { ROUTES } from './config/routes.ts'
import Login from './screens/Login.tsx'
import Register from './screens/Register.tsx'
import Services from './screens/Services.tsx'
import ServiceGroups from './screens/ServiceGroups.tsx'
import Providers from './screens/Providers.tsx'
import Planning from './screens/Planning.tsx'
import Formations from './screens/Formations.tsx'
import FormationDetail from './screens/FormationDetail.tsx'
import FormationsCompare from './screens/FormationsCompare.tsx'

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false } },
})

function protect(element: React.ReactNode) {
  return <RequireAuth>{element}</RequireAuth>
}

function authPage(element: React.ReactNode) {
  return <RedirectIfAuthenticated>{element}</RedirectIfAuthenticated>
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Router>
          <div className="p-4">
            <h1 className="text-3xl font-bold text-center mb-8">
              Формування пакетів сервісів для провайдерів інфокомунікацій
            </h1>

            <Navbar />

            <Routes>
              {/* Home → formations (RequireAuth bounces anon users to /login). */}
              <Route path="/" element={<Navigate to={ROUTES.formations} replace />} />

              {/* Auth — bounce already-authenticated users to the app home. */}
              <Route path={ROUTES.login} element={authPage(<Login />)} />
              <Route path={ROUTES.register} element={authPage(<Register />)} />

              {/* Information system — authenticated */}
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
      </AuthProvider>
    </QueryClientProvider>
  )
}

export default App
