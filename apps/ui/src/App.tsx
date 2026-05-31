import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'sonner'

import Navbar from './components/Navbar.tsx'
import { AuthProvider } from './auth/AuthContext.tsx'
import RequireAuth from './auth/RequireAuth.tsx'
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
              <Route path="/" element={<Navigate to="/formations" replace />} />

              {/* Auth */}
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />

              {/* Information system — authenticated */}
              <Route path="/services" element={protect(<Services />)} />
              <Route path="/service-groups" element={protect(<ServiceGroups />)} />
              <Route path="/providers" element={protect(<Providers />)} />
              <Route path="/planning" element={protect(<Planning />)} />
              <Route path="/formations" element={protect(<Formations />)} />
              <Route path="/formations/compare" element={protect(<FormationsCompare />)} />
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
