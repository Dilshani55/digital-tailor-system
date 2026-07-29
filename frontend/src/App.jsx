import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Navbar         from './components/Navbar';
import Sidebar        from './components/Sidebar';
import Login          from './pages/Login';
import Register       from './pages/Register';
import Dashboard      from './pages/Dashboard';
import Upload         from './pages/Upload';
import History        from './pages/History';
import Measurements   from './pages/Measurements';
import LoadingSpinner from './components/LoadingSpinner';

// Protected route wrapper with Sidebar layout
function ProtectedLayout({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <LoadingSpinner />;
  if (!user) return <Navigate to="/login" />;

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
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
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
      <Route path="/" element={
        <Navigate to={user ? '/dashboard' : '/login'} />
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
