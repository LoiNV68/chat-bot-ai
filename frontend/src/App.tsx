import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Suspense, lazy } from 'react';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import { Disc } from 'lucide-react';

// Lazy load các trang để tối ưu bundle size
const Login = lazy(() => import('./pages/auth/Login'));
const ChatLayout = lazy(() => import('./pages/chat/ChatLayout'));
const DocumentManager = lazy(() => import('./pages/admin/DocumentManager'));
const UserManager = lazy(() => import('./pages/admin/UserManager'));

// Component loading hiển thị khi đang tải trang
const PageLoader = () => (
  <div className="flex min-h-screen items-center justify-center bg-slate-950 text-cyan-500">
    <Disc className="h-10 w-10 animate-spin" />
  </div>
);

function App() {
  return (
    <AuthProvider>
      <Router>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route path="/login" element={<Login />} />
            
            {/* Các Route được bảo vệ */}
            <Route element={<ProtectedRoute />}>
                <Route path="/chat" element={<ChatLayout />} />
            </Route>

            {/* Các Route dành cho Admin */}
            <Route element={<ProtectedRoute requireAdmin={true} />}>
                <Route path="/admin" element={<DocumentManager />} />
                <Route path="/admin/users" element={<UserManager />} />
            </Route>

            <Route path="/" element={<Navigate to="/chat" replace />} />
          </Routes>
        </Suspense>
      </Router>
    </AuthProvider>
  );
}

export default App;

