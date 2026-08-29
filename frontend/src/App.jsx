import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Navbar         from './components/Navbar';
import Sidebar        from './components/Sidebar';
import Home           from './pages/Home';
import Auth           from './pages/Auth';
import Dashboard      from './pages/Dashboard';
import Upload         from './pages/Upload';
import History        from './pages/History';
import Measurements   from './pages/Measurements';
import Customers      from './pages/Customers';
import Settings       from './pages/Settings';
import ResearcherDashboard from './pages/ResearcherDashboard';
import LoadingSpinner from './components/LoadingSpinner';

// Protected route wrapper with Sidebar layout
function ProtectedLayout({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <LoadingSpinner />;
  if (!user) return <Navigate to="/auth" />;

  return (
    <div className="app">
      <Navbar />
      <div className="app-body">
        <Sidebar />
        <main className="main-content">
          {children}
        </main>
      </div>
    </div>
  );
}

function AppRoutes() {
  const { user, loading } = useAuth();
  if (loading) return <LoadingSpinner />;

  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/auth" element={<Auth />} />
      <Route path="/login" element={<Navigate to="/auth" />} />
      <Route path="/register" element={<Navigate to="/auth" />} />
      <Route path="/dashboard" element={
        <ProtectedLayout><Dashboard /></ProtectedLayout>
      }/>
      <Route path="/upload" element={
        <ProtectedLayout><Upload /></ProtectedLayout>
      }/>
      <Route path="/history" element={
        <ProtectedLayout><History /></ProtectedLayout>
      }/>
      <Route path="/measurements" element={
        <ProtectedLayout><Measurements /></ProtectedLayout>
      }/>
      <Route path="/customers" element={
        <ProtectedLayout><Customers /></ProtectedLayout>
      }/>
      <Route path="/settings" element={
        <ProtectedLayout><Settings /></ProtectedLayout>
      }/>
      <Route path="/researcher" element={
        <ProtectedLayout><ResearcherDashboard /></ProtectedLayout>
      }/>
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
