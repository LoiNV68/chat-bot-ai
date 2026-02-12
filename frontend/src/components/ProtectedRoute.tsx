import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Disc } from 'lucide-react';

interface ProtectedRouteProps {
    requireAdmin?: boolean;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ requireAdmin = false }) => {
    const { isAuthenticated, isLoading, user } = useAuth();

    if (isLoading) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-slate-950 text-cyan-500">
                <Disc className="h-10 w-10 animate-spin" />
            </div>
        );
    }

    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    if (requireAdmin && !user?.is_superuser && user?.role !== 'admin' && user?.role !== 'lecturer') {
        // Chuyển hướng đến chat nếu không phải admin hoặc giảng viên
        return <Navigate to="/chat" replace />;
    }

    return <Outlet />;
};

export default ProtectedRoute;
