import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Users, UserPlus, Shield, ShieldOff, Activity, Search, ArrowLeft, UserX, UserCheck, X, GraduationCap, Eye, EyeOff } from 'lucide-react';
import { cn } from '@/lib/utils';
import axios from 'axios';
import { API_ENDPOINTS } from '@/config/api';
import { useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import ConfirmModal from '@/components/ConfirmModal';

type UserRole = 'admin' | 'lecturer' | 'user';

interface User {
    id: number;
    email: string;
    full_name: string | null;
    is_active: boolean;
    is_superuser: boolean;
    role: UserRole;
}

const UserManager = () => {
    const navigate = useNavigate();
    const [users, setUsers] = useState<User[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    
    // Modal tạo người dùng
    const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
    const [newUser, setNewUser] = useState({ email: '', password: '', full_name: '', is_superuser: false, role: 'user' as UserRole });
    const [creating, setCreating] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
    
    // Modal xác nhận
    const [confirmModal, setConfirmModal] = useState<{ isOpen: boolean; title: string; message: string; onConfirm: () => void }>({
        isOpen: false, title: '', message: '', onConfirm: () => {}
    });

    useEffect(() => {
        fetchUsers();
    }, []);

    const fetchUsers = async () => {
        setIsLoading(true);
        try {
            const token = localStorage.getItem('token');
            const response = await axios.get(API_ENDPOINTS.USERS.BASE, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setUsers(response.data);
        } catch (error) {
            console.error('Error fetching users:', error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleCreateUser = async () => {
        // Reset lỗi
        setErrors({});
        
        // Xác thực
        const newErrors: { email?: string; password?: string } = {};
        
        if (!newUser.email) {
            newErrors.email = 'Vui lòng nhập email';
        } else {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(newUser.email)) {
                newErrors.email = 'Email không hợp lệ (ví dụ: abc@example.com)';
            }
        }
        
        if (!newUser.password) {
            newErrors.password = 'Vui lòng nhập mật khẩu';
        } else if (newUser.password.length < 4) {
            newErrors.password = 'Mật khẩu phải có ít nhất 4 ký tự';
        }
        
        if (Object.keys(newErrors).length > 0) {
            setErrors(newErrors);
            return;
        }
        
        setCreating(true);
        try {
            const token = localStorage.getItem('token');
            await axios.post(API_ENDPOINTS.USERS.BASE, newUser, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setIsCreateModalOpen(false);
            setNewUser({ email: '', password: '', full_name: '', is_superuser: false, role: 'user' });
            setErrors({});
            fetchUsers();
        } catch (error: any) {
            setErrors({ email: error.response?.data?.detail || 'Lỗi khi tạo tài khoản' });
        } finally {
            setCreating(false);
        }
    };

    const handleToggleAdmin = async (userId: number, currentStatus: boolean) => {
        setConfirmModal({
            isOpen: true,
            title: currentStatus ? 'Gỡ quyền Admin' : 'Cấp quyền Admin',
            message: currentStatus 
                ? 'Bạn có chắc chắn muốn gỡ quyền Admin của người dùng này?' 
                : 'Bạn có chắc chắn muốn cấp quyền Admin cho người dùng này?',
            onConfirm: async () => {
                try {
                    const token = localStorage.getItem('token');
                    await axios.patch(API_ENDPOINTS.USERS.TOGGLE_ADMIN(userId), {}, {
                        headers: { Authorization: `Bearer ${token}` }
                    });
                    fetchUsers();
                } catch (error: any) {
                    alert(error.response?.data?.detail || 'Lỗi khi thay đổi quyền');
                }
                setConfirmModal(prev => ({ ...prev, isOpen: false }));
            }
        });
    };

    const handleToggleActive = async (userId: number, currentStatus: boolean) => {
        setConfirmModal({
            isOpen: true,
            title: currentStatus ? 'Vô hiệu hóa tài khoản' : 'Kích hoạt tài khoản',
            message: currentStatus 
                ? 'Bạn có chắc chắn muốn vô hiệu hóa tài khoản này?' 
                : 'Bạn có chắc chắn muốn kích hoạt lại tài khoản này?',
            onConfirm: async () => {
                try {
                    const token = localStorage.getItem('token');
                    await axios.patch(API_ENDPOINTS.USERS.TOGGLE_ACTIVE(userId), {}, {
                        headers: { Authorization: `Bearer ${token}` }
                    });
                    fetchUsers();
                } catch (error: any) {
                    alert(error.response?.data?.detail || 'Lỗi khi thay đổi trạng thái');
                }
                setConfirmModal(prev => ({ ...prev, isOpen: false }));
            }
        });
    };

    const filteredUsers = users.filter(user => 
        user.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (user.full_name?.toLowerCase().includes(searchQuery.toLowerCase()))
    );

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-cyan-950">
            <div className="container mx-auto py-8 px-4">
                {/* Header */}
                <div className="flex items-center justify-between mb-8">
                    <div className="flex items-center gap-4">
                        <Button 
                            variant="ghost" 
                            onClick={() => navigate('/chat')}
                            className="text-slate-400 hover:text-cyan-400"
                        >
                            <ArrowLeft className="h-5 w-5 mr-2" />
                            Quay lại
                        </Button>
                        <div>
                            <h1 className="text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
                                Quản lý người dùng
                            </h1>
                            <p className="text-slate-400 mt-1">Tạo tài khoản và phân quyền cho người dùng</p>
                        </div>
                    </div>
                    <Button 
                        onClick={() => setIsCreateModalOpen(true)}
                        className="bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500"
                    >
                        <UserPlus className="h-4 w-4 mr-2" />
                        Tạo tài khoản
                    </Button>
                </div>

                {/* Thẻ thống kê */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                    <Card className="bg-slate-900/50 border-slate-800">
                        <CardContent className="p-4 flex items-center gap-4">
                            <div className="p-3 rounded-lg bg-cyan-500/10">
                                <Users className="h-6 w-6 text-cyan-400" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold text-white">{users.length}</p>
                                <p className="text-slate-400 text-sm">Tổng người dùng</p>
                            </div>
                        </CardContent>
                    </Card>
                    {/* <Card className="bg-slate-900/50 border-slate-800">
                        <CardContent className="p-4 flex items-center gap-4">
                            <div className="p-3 rounded-lg bg-purple-500/10">
                                <Shield className="h-6 w-6 text-purple-400" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold text-white">{users.filter(u => u.is_superuser).length}</p>
                                <p className="text-slate-400 text-sm">Quản trị viên</p>
                            </div>
                        </CardContent>
                    </Card> */}
                    <Card className="bg-slate-900/50 border-slate-800">
                        <CardContent className="p-4 flex items-center gap-4">
                            <div className="p-3 rounded-lg bg-green-500/10">
                                <Activity className="h-6 w-6 text-green-400" />
                            </div>
                            <div>
                                <p className="text-2xl font-bold text-white">{users.filter(u => u.is_active).length}</p>
                                <p className="text-slate-400 text-sm">Đang hoạt động</p>
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Tìm kiếm */}
                <div className="relative mb-6">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                        placeholder="Tìm kiếm theo email hoặc tên..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="pl-10 bg-slate-900/50 border-slate-700 text-white placeholder:text-slate-500"
                    />
                </div>

                {/* Bảng người dùng */}
                <Card className="bg-slate-900/50 border-slate-800">
                    <CardContent className="p-0">
                        <table className="w-full">
                            <thead>
                                <tr className="border-b border-slate-700/50">
                                    <th className="text-left p-4 text-slate-400 font-medium">Người dùng</th>
                                    <th className="text-left p-4 text-slate-400 font-medium">Email</th>
                                    <th className="text-left p-4 text-slate-400 font-medium">Vai trò</th>
                                    <th className="text-left p-4 text-slate-400 font-medium">Trạng thái</th>
                                    <th className="text-right p-4 text-slate-400 font-medium">Hành động</th>
                                </tr>
                            </thead>
                            <tbody>
                                {isLoading ? (
                                    <tr>
                                        <td colSpan={5} className="text-center py-8 text-slate-400">
                                            Đang tải...
                                        </td>
                                    </tr>
                                ) : filteredUsers.length === 0 ? (
                                    <tr>
                                        <td colSpan={5} className="text-center py-8 text-slate-400">
                                            Không tìm thấy người dùng
                                        </td>
                                    </tr>
                                ) : (
                                    filteredUsers.map((user) => (
                                        <tr key={user.id} className="group hover:bg-cyan-500/5 transition-colors border-b border-slate-800/50">
                                            <td className="p-4">
                                                <div className="flex items-center gap-3">
                                                    <div className={cn(
                                                        "h-10 w-10 rounded-full flex items-center justify-center text-white font-medium",
                                                        user.is_superuser ? "bg-purple-600" : "bg-slate-600"
                                                    )}>
                                                        {user.full_name?.[0]?.toUpperCase() || user.email[0].toUpperCase()}
                                                    </div>
                                                    <span className="text-white font-medium">{user.full_name || 'Chưa đặt tên'}</span>
                                                </div>
                                            </td>
                                            <td className="p-4 text-slate-300">{user.email}</td>
                                            <td className="p-4">
                                                <span className={cn(
                                                    "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border",
                                                    user.role === 'admin' || user.is_superuser
                                                        ? "bg-purple-500/10 text-purple-400 border-purple-500/20" 
                                                        : user.role === 'lecturer'
                                                        ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/20"
                                                        : "bg-slate-500/10 text-slate-400 border-slate-500/20"
                                                )}>
                                                    {user.role === 'admin' || user.is_superuser ? <Shield className="h-3 w-3" /> : user.role === 'lecturer' ? <GraduationCap className="h-3 w-3" /> : <Users className="h-3 w-3" />}
                                                    {user.role === 'admin' || user.is_superuser ? 'Admin' : user.role === 'lecturer' ? 'Giảng viên' : 'User'}
                                                </span>
                                            </td>
                                            <td className="p-4">
                                                <span className={cn(
                                                    "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border",
                                                    user.is_active 
                                                        ? "bg-green-500/10 text-green-400 border-green-500/20" 
                                                        : "bg-red-500/10 text-red-400 border-red-500/20"
                                                )}>
                                                    <Activity className="h-3 w-3" />
                                                    {user.is_active ? 'Hoạt động' : 'Đã khóa'}
                                                </span>
                                            </td>
                                            <td className="p-4 text-right">
                                                <div className="flex justify-end gap-1">
                                                    <Button
                                                        size="sm"
                                                        variant="ghost"
                                                        onClick={() => handleToggleAdmin(user.id, user.is_superuser)}
                                                        className="text-slate-400 hover:text-purple-400 hover:bg-purple-500/10"
                                                        title={user.is_superuser ? 'Gỡ Admin' : 'Cấp Admin'}
                                                    >
                                                        {user.is_superuser ? <ShieldOff className="h-4 w-4" /> : <Shield className="h-4 w-4" />}
                                                    </Button>
                                                    <Button
                                                        size="sm"
                                                        variant="ghost"
                                                        onClick={() => handleToggleActive(user.id, user.is_active)}
                                                        className={cn(
                                                            "hover:bg-opacity-10",
                                                            user.is_active 
                                                                ? "text-slate-400 hover:text-red-400 hover:bg-red-500/10" 
                                                                : "text-slate-400 hover:text-green-400 hover:bg-green-500/10"
                                                        )}
                                                        title={user.is_active ? 'Khóa tài khoản' : 'Mở khóa'}
                                                    >
                                                        {user.is_active ? <UserX className="h-4 w-4" /> : <UserCheck className="h-4 w-4" />}
                                                    </Button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </CardContent>
                </Card>
            </div>

            {/* Modal tạo người dùng */}
            {isCreateModalOpen && (
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
                    <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-md">
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-xl font-semibold text-white">Tạo tài khoản mới</h2>
                            <Button variant="ghost" size="sm" onClick={() => setIsCreateModalOpen(false)}>
                                <X className="h-4 w-4" />
                            </Button>
                        </div>
                        <div className="space-y-4">
                            <div>
                                <label className="text-sm text-slate-400 mb-1 block">Họ tên</label>
                                <Input
                                    placeholder="Nguyễn Văn A"
                                    value={newUser.full_name}
                                    onChange={(e) => setNewUser({ ...newUser, full_name: e.target.value })}
                                    className="bg-slate-800 border-slate-700 text-white"
                                />
                            </div>
                            <div>
                                <label className="text-sm text-slate-400 mb-1 block">Email *</label>
                                <Input
                                    type="email"
                                    placeholder="email@example.com"
                                    value={newUser.email}
                                    onChange={(e) => {
                                        setNewUser({ ...newUser, email: e.target.value });
                                        if (errors.email) setErrors({ ...errors, email: undefined });
                                    }}
                                    className={`bg-slate-800 border-slate-700 text-white ${errors.email ? 'border-red-500' : ''}`}
                                />
                                {errors.email && <p className="text-red-400 text-xs mt-1">{errors.email}</p>}
                            </div>
                            <div>
                                <label className="text-sm text-slate-400 mb-1 block">Mật khẩu *</label>
                                <div className="relative">
                                    <Input
                                        type={showPassword ? "text" : "password"}
                                        placeholder="••••••••"
                                        value={newUser.password}
                                        onChange={(e) => {
                                            setNewUser({ ...newUser, password: e.target.value });
                                            if (errors.password) setErrors({ ...errors, password: undefined });
                                        }}
                                        className={`bg-slate-800 border-slate-700 text-white pr-10 ${errors.password ? 'border-red-500' : ''}`}
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowPassword(!showPassword)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200"
                                    >
                                        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                    </button>
                                </div>
                                {errors.password && <p className="text-red-400 text-xs mt-1">{errors.password}</p>}
                            </div>
                            <div>
                                <label className="text-sm text-slate-400 mb-1 block">Vai trò *</label>
                                <select
                                    value={newUser.role}
                                    onChange={(e) => setNewUser({ 
                                        ...newUser, 
                                        role: e.target.value as UserRole,
                                        is_superuser: e.target.value === 'admin'
                                    })}
                                    className="w-full h-10 px-3 rounded-md bg-slate-800 border border-slate-700 text-white"
                                >
                                    <option value="user">Sinh viên</option>
                                    <option value="lecturer">Giảng viên</option>
                                    {/* <option value="admin">Quản trị viên</option> */}
                                </select>
                            </div>
                        </div>
                        <div className="flex justify-end gap-2 mt-6">
                            <Button variant="ghost" onClick={() => setIsCreateModalOpen(false)} className="text-slate-300 hover:text-white hover:bg-slate-700">
                                Hủy
                            </Button>
                            <Button 
                                onClick={handleCreateUser} 
                                disabled={creating || !newUser.email || !newUser.password}
                                className="bg-gradient-to-r from-cyan-600 to-blue-600 text-white hover:from-cyan-500 hover:to-blue-500"
                            >
                                {creating ? 'Đang tạo...' : 'Tạo tài khoản'}
                            </Button>
                        </div>
                    </div>
                </div>
            )}

            {/* Modal xác nhận */}
            <ConfirmModal
                isOpen={confirmModal.isOpen}
                title={confirmModal.title}
                message={confirmModal.message}
                onConfirm={confirmModal.onConfirm}
                onCancel={() => setConfirmModal(prev => ({ ...prev, isOpen: false }))}
            />
        </div>
    );
};

export default UserManager;
