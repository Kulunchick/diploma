import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { Toaster } from 'sonner'

import Navbar from './components/Navbar.tsx'
import { AuthProvider } from './auth/AuthContext.tsx'
import RequireAuth from './auth/RequireAuth.tsx'
import Solve from './screens/Solve.tsx'
import Experiment1 from './screens/Experiment1.tsx'
import Experiment2 from './screens/Experiment2.tsx'
import Experiment3 from './screens/Experiment3.tsx'
import Experiment4 from './screens/Experiment4.tsx'
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
              {/* Legacy, unauthenticated — unchanged */}
              <Route path="/" element={<Solve />} />
              <Route path="/experiment1" element={<Experiment1 />} />
              <Route path="/experiment2" element={<Experiment2 />} />
              <Route path="/experiment3" element={<Experiment3 />} />
              <Route path="/experiment4" element={<Experiment4 />} />

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
