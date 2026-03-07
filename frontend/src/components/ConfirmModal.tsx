import React from 'react';
import { X, AlertTriangle } from 'lucide-react';
import { Button } from './ui/button';
import { cn } from '@/lib/utils';

interface ConfirmModalProps {
    isOpen: boolean;
    title: string;
    message: string;
    confirmText?: string;
    cancelText?: string;
    onConfirm: () => void | Promise<void>;
    onCancel: () => void;
    type?: 'danger' | 'info' | 'warning';
    showCancel?: boolean;
    isLoading?: boolean;
}

const ConfirmModal: React.FC<ConfirmModalProps> = ({
    isOpen,
    title,
    message,
    confirmText = 'Xác nhận',
    cancelText = 'Hủy',
    onConfirm,
    onCancel,
    type = 'danger',
    showCancel = true,
    isLoading = false
}) => {
    if (!isOpen) return null;

    const typeConfig = {
        danger: {
            icon: <AlertTriangle className="h-6 w-6 text-red-500" />,
            buttonClass: "bg-red-600 hover:bg-red-700 text-white shadow-[0_0_15px_-3px_rgba(239,68,68,0.4)]",
            titleClass: "text-red-500"
        },
        info: {
            icon: <AlertTriangle className="h-6 w-6 text-cyan-500" />,
            buttonClass: "bg-cyan-600 hover:bg-cyan-700 text-white shadow-[0_0_15px_-3px_rgba(6,182,212,0.4)]",
            titleClass: "text-cyan-500"
        },
        warning: {
            icon: <AlertTriangle className="h-6 w-6 text-yellow-500" />,
            buttonClass: "bg-yellow-600 hover:bg-yellow-700 text-white shadow-[0_0_15px_-3px_rgba(234,179,8,0.4)]",
            titleClass: "text-yellow-500"
        }
    };

    const config = typeConfig[type];

    return (
        <div className="fixed inset-0 z-[110] flex items-center justify-center p-4">
            {/* Nền mờ */}
            <div 
                className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-300" 
                onClick={onCancel}
            />

            {/* Nội dung Modal */}
            <div className="relative z-10 w-full max-w-md overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/90 shadow-2xl animate-in zoom-in-95 duration-200">
                 {/* Đường viền trang trí phía trên */}
                 <div className={cn(
                     "h-1 w-full",
                     type === 'danger' ? "bg-red-600" : type === 'warning' ? "bg-yellow-600" : "bg-cyan-600"
                 )} />

                 <div className="p-6">
                    <div className="flex items-start gap-4">
                        <div className={cn(
                            "mt-1 p-2 rounded-xl border",
                            type === 'danger' ? "bg-red-500/10 border-red-500/20" : type === 'warning' ? "bg-yellow-500/10 border-yellow-500/20" : "bg-cyan-500/10 border-cyan-500/20"
                        )}>
                            {config.icon}
                        </div>
                        <div className="flex-1 space-y-2">
                            <h3 className={cn("text-xl font-bold tracking-tight", config.titleClass)}>
                                {title}
                            </h3>
                            <p className="text-slate-400 leading-relaxed">
                                {message}
                            </p>
                        </div>
                        <button 
                            onClick={onCancel} 
                            className="text-slate-500 hover:text-white transition-colors"
                        >
                            <X className="h-5 w-5" />
                        </button>
                    </div>

                    <div className="mt-8 flex flex-col-reverse sm:flex-row sm:justify-end gap-3">
                        {showCancel && (
                            <Button 
                                variant="ghost" 
                                onClick={onCancel}
                                disabled={isLoading}
                                className="w-full sm:w-auto text-slate-400 hover:text-white hover:bg-slate-800 transition-all font-medium py-2.5"
                            >
                                {cancelText}
                            </Button>
                        )}
                        <Button 
                            onClick={async () => {
                                await onConfirm();
                                if (!showCancel) onCancel(); // Auto close if alert mode
                            }}
                            disabled={isLoading}
                            className={cn(
                                "w-full sm:w-auto font-bold py-2.5 px-6 transition-all",
                                config.buttonClass
                            )}
                        >
                            {isLoading ? (
                                <div className="flex items-center gap-2">
                                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white" />
                                    <span>Đang xử lý...</span>
                                </div>
                            ) : (
                                confirmText
                            )}
                        </Button>
                    </div>
                 </div>
            </div>
        </div>
    );
};

export default ConfirmModal;
