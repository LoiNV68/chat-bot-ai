import React, { useState, useEffect } from 'react';
import { X, Pencil, Loader2 } from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';

interface RenameModalProps {
    isOpen: boolean;
    title: string;
    initialValue: string;
    onRename: (newValue: string) => Promise<void>;
    onCancel: () => void;
    placeholder?: string;
    isLoading?: boolean;
}

const RenameModal: React.FC<RenameModalProps> = ({
    isOpen,
    title,
    initialValue,
    onRename,
    onCancel,
    placeholder = 'Nhập tên mới...',
    isLoading = false
}) => {
    const [value, setValue] = useState(initialValue);

    useEffect(() => {
        if (isOpen) {
            setValue(initialValue);
        }
    }, [isOpen, initialValue]);

    if (!isOpen) return null;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (value.trim() && value !== initialValue) {
            await onRename(value.trim());
        }
        onCancel();
    };

    return (
        <div className="fixed inset-0 z-[110] flex items-center justify-center p-4">
            {/* Backdrop */}
            <div 
                className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-300" 
                onClick={onCancel}
            />

            {/* Modal Content */}
            <form 
                onSubmit={handleSubmit}
                className="relative z-10 w-full max-w-md overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/90 shadow-2xl animate-in zoom-in-95 duration-200"
            >
                 {/* Top Decor Line */}
                 <div className="h-1 w-full bg-cyan-600" />

                 <div className="p-6">
                    <div className="flex items-start justify-between gap-4 mb-6">
                        <div className="flex items-center gap-3">
                            <div className="p-2 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
                                <Pencil className="h-5 w-5" />
                            </div>
                            <h3 className="text-xl font-bold tracking-tight text-white">
                                {title}
                            </h3>
                        </div>
                        <button 
                            type="button"
                            onClick={onCancel} 
                            className="text-slate-500 hover:text-white transition-colors"
                        >
                            <X className="h-5 w-5" />
                        </button>
                    </div>

                    <div className="space-y-4">
                        <div className="space-y-2">
                             <Input 
                                autoFocus
                                value={value}
                                onChange={(e) => setValue(e.target.value)}
                                placeholder={placeholder}
                                className="bg-slate-950/50 border-slate-700 text-slate-100 focus:border-cyan-500/50 focus:ring-cyan-500/20 py-6"
                             />
                        </div>
                    </div>

                    <div className="mt-8 flex flex-col-reverse sm:flex-row sm:justify-end gap-3">
                        <Button 
                            type="button"
                            variant="ghost" 
                            onClick={onCancel}
                            className="w-full sm:w-auto text-slate-400 hover:text-white hover:bg-slate-800 transition-all font-medium py-2.5"
                        >
                            Hủy
                        </Button>
                        <Button 
                            type="submit"
                            disabled={isLoading || !value.trim() || value === initialValue}
                            className="w-full sm:w-auto bg-cyan-600 hover:bg-cyan-700 text-white shadow-[0_0_15px_-3px_rgba(6,182,212,0.4)] font-bold py-2.5 px-6 transition-all"
                        >
                            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Lưu thay đổi'}
                        </Button>
                    </div>
                 </div>
            </form>
        </div>
    );
};

export default RenameModal;
