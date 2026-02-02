import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/auth/Login';
import ChatLayout from './pages/chat/ChatLayout';
import DocumentManager from './pages/admin/DocumentManager';
import UserManager from './pages/admin/UserManager';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />
          
          {/* Protected Routes */}
          <Route element={<ProtectedRoute />}>
              <Route path="/chat" element={<ChatLayout />} />
          </Route>

          {/* Admin Routes */}
          <Route element={<ProtectedRoute requireAdmin={true} />}>
              <Route path="/admin" element={<DocumentManager />} />
              <Route path="/admin/users" element={<UserManager />} />
          </Route>

          <Route path="/" element={<Navigate to="/chat" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
