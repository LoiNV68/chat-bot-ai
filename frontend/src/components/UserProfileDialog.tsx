import React from 'react';
import { X, User, Mail, CreditCard, Activity } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { Button } from './ui/button';

interface UserProfileDialogProps {
    isOpen: boolean;
    onClose: () => void;
}

const UserProfileDialog: React.FC<UserProfileDialogProps> = ({ isOpen, onClose }) => {
    const { user } = useAuth();
    
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center">
            {/* Backdrop */}
            <div 
                className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm animate-in fade-in duration-200" 
                onClick={onClose}
            />

            {/* Modal Content */}
            <div className="relative z-10 w-full max-w-md overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/90 shadow-2xl animate-in zoom-in-95 duration-200 p-0">
                 {/* Header Decor */}
                 <div className="h-24 bg-gradient-to-r from-cyan-600 to-blue-600 relative overflow-hidden">
                    <div className="absolute inset-0 bg-[linear-gradient(45deg,transparent_25%,rgba(255,255,255,0.1)_50%,transparent_75%,transparent_100%)] bg-[size:20px_20px]" />
                    <div className="absolute -bottom-8 left-6">
                        <div className="h-20 w-20 rounded-full border-4 border-slate-900 bg-slate-800 flex items-center justify-center shadow-lg">
                            <User className="h-10 w-10 text-cyan-400" />
                        </div>
                    </div>
                    <button 
                        onClick={onClose} 
                        className="absolute top-2 right-2 p-2 rounded-full bg-black/20 text-white/70 hover:bg-black/40 hover:text-white transition-all"
                    >
                        <X className="h-4 w-4" />
                    </button>
                 </div>

                 <div className="pt-14 px-6 pb-6">
                     <div className="mb-6">
                        <h2 className="text-2xl font-bold text-white">{user?.full_name}</h2>
                        <div className="flex items-center gap-2 mt-1">
                            <span className="text-sm text-slate-400">{user?.email}</span>
                            {user?.is_superuser && (
                                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 uppercase tracking-wide">
                                    ADMIN
                                </span>
                            )}
                        </div>
                     </div>

                     <div className="space-y-4">
                        <div className="flex items-center gap-3 p-3 rounded-lg bg-white/5 border border-white/5 hover:border-cyan-500/30 transition-colors">
                            <div className="h-8 w-8 rounded-lg bg-blue-500/20 flex items-center justify-center text-blue-400">
                                <Mail className="h-4 w-4" />
                            </div>
                            <div>
                                <p className="text-xs text-slate-500 uppercase font-semibold">Email Liên hệ</p>
                                <p className="text-sm text-slate-200">{user?.email}</p>
                            </div>
                        </div>

                        <div className="flex items-center gap-3 p-3 rounded-lg bg-white/5 border border-white/5 hover:border-cyan-500/30 transition-colors">
                            <div className="h-8 w-8 rounded-lg bg-purple-500/20 flex items-center justify-center text-purple-400">
                                <CreditCard className="h-4 w-4" />
                            </div>
                            <div>
                                <p className="text-xs text-slate-500 uppercase font-semibold">ID Người dùng</p>
                                <p className="text-sm text-slate-200 font-mono">USER_#{user?.id.toString().padStart(4, '0')}</p>
                            </div>
                        </div>

                        <div className="flex items-center gap-3 p-3 rounded-lg bg-white/5 border border-white/5 hover:border-cyan-500/30 transition-colors">
                            <div className="h-8 w-8 rounded-lg bg-green-500/20 flex items-center justify-center text-green-400">
                                <Activity className="h-4 w-4" />
                            </div>
                            <div>
                                <p className="text-xs text-slate-500 uppercase font-semibold">Trạng thái</p>
                                <div className="flex items-center gap-2 mt-0.5">
                                    <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
                                    <span className="text-sm text-green-400 font-medium">Đang hoạt động</span>
                                </div>
                            </div>
                        </div>
                     </div>

                     <div className="mt-8">
                         <Button onClick={onClose} className="w-full bg-slate-800 hover:bg-slate-700 text-slate-200">
                             Đóng
                         </Button>
                     </div>
                 </div>
            </div>
        </div>
    );
};

export default UserProfileDialog;
