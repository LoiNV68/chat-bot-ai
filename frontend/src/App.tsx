import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Login from './pages/auth/Login';
import ChatLayout from './pages/chat/ChatLayout';
import DocumentManager from './pages/admin/DocumentManager';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/chat" element={<ChatLayout />} />
        <Route path="/admin" element={<DocumentManager />} />
        <Route path="/" element={<Login />} />
      </Routes>
    </Router>
  );
}

export default App;
