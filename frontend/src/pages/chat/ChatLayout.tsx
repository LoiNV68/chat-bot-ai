import React, { useState } from 'react';
import { Send, Bot, User, Plus, MessageSquare, Settings, Menu, LogOut, Shield } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import axios from 'axios';
import { useAuth } from '@/context/AuthContext';
import { useNavigate } from 'react-router-dom';
import UserProfileDialog from '@/components/UserProfileDialog';

const ChatLayout = () => {
    const { user, logout } = useAuth();
    const navigate = useNavigate();
    const [isSettingsOpen, setIsSettingsOpen] = useState(false);
    const [isProfileOpen, setIsProfileOpen] = useState(false);
    const [messages, setMessages] = useState<{ role: string; content: string }[]>([
        // { role: 'user', content: 'Xin chào, bạn có thể giúp tôi viết code không?' },
        // { role: 'ai', content: 'Chắc chắn rồi! Tôi đã cập nhật các công nghệ mới nhất. Bạn đang làm việc cụ thể về vấn đề gì?' },
    ]);
    const [inputValue, setInputValue] = useState('');
    const [isTyping, setIsTyping] = useState(false);

    const handleSendMessage = async () => {
        if (!inputValue.trim()) return;
        
        const newMessages = [...messages, { role: 'user', content: inputValue }];
        setMessages(newMessages);
        setInputValue('');
        setIsTyping(true);

        try {
            const token = localStorage.getItem('token');
            const response = await axios.post(
                'http://localhost:8000/api/v1/chat/completion',
                {
                    query: inputValue,
                    history: newMessages.map(m => m.content) // simplified history
                },
                {
                    headers: { Authorization: `Bearer ${token}` }
                }
            );

            setMessages(prev => [...prev, { role: 'ai', content: response.data.answer }]);

        } catch (error) {
            console.error('Chat error:', error);
            setMessages(prev => [...prev, { role: 'ai', content: 'Xin lỗi, hệ thống đang gặp sự cố.' }]);
        } finally {
            setIsTyping(false);
        }
    };

    return (
        <div className="relative flex h-screen overflow-hidden bg-slate-950 font-sans text-slate-100 selection:bg-cyan-500/30">
            {/* Background Effects (Consistent with Login) */}
            <div className="absolute inset-0 z-0 pointer-events-none">
                <div className="absolute top-[-20%] left-[-10%] h-[500px] w-[500px] rounded-full bg-cyan-500/10 blur-[120px] animate-pulse" />
                <div className="absolute bottom-[-20%] right-[-10%] h-[500px] w-[500px] rounded-full bg-blue-600/10 blur-[120px] animate-pulse delay-1000" />
                <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:40px_40px] [mask-image:radial-gradient(ellipse_80%_80%_at_50%_50%,#000_70%,transparent_100%)]" />
            </div>

            {/* Sidebar */}
            <div className="z-10 hidden w-72 flex-col border-r border-slate-800 bg-slate-900/60 backdrop-blur-xl md:flex">
                <div className="flex h-16 items-center border-b border-slate-800 px-6">
                    <span className="text-lg font-bold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-500">
                        AI CHAT-BOT
                    </span>
                </div>
                
                <div className="p-4">
                    <Button className="w-full justify-start gap-2 bg-gradient-to-r from-cyan-600/20 to-blue-600/20 border border-cyan-500/30 text-cyan-400 hover:text-cyan-300 hover:border-cyan-400 hover:bg-cyan-500/10 transition-all font-medium">
                        <Plus className="h-4 w-4" />
                        CUỘC TRÒ CHUYỆN MỚI
                    </Button>
                </div>

                <div className="flex-1 overflow-y-auto px-2 py-2">
                    <h3 className="mb-2 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500">NHẬT KÝ GẦN ĐÂY</h3>
                    <div className="space-y-1">
                        {[1, 2, 3].map((i) => (
                            <button key={i} className="flex w-full items-center gap-3 rounded-lg px-4 py-3 text-sm text-slate-400 transition-all hover:bg-white/5 hover:text-cyan-200">
                                <MessageSquare className="h-4 w-4 opacity-70" />
                                <span className="truncate">Nhật ký hệ thống #{i}</span>
                            </button>
                        ))}
                    </div>
                </div>

                <div className="border-t border-slate-800 p-4 relative">
                    {/* Settings Dropdown */}
                    {isSettingsOpen && (
                        <div className="absolute bottom-full left-4 right-4 mb-2 rounded-xl border border-slate-700 bg-slate-900/95 backdrop-blur-xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200 z-50">
                            {/* Profile Info Button */}
                            <button
                                onClick={() => setIsProfileOpen(true)}
                                className="flex w-full items-center gap-3 px-4 py-3 text-sm text-slate-200 hover:bg-slate-800 transition-colors border-b border-slate-800/50"
                            >
                                <User className="h-4 w-4 text-slate-400" />
                                <span>Thông tin cá nhân</span>
                            </button>

                            {/* Admin Link */}
                            {user?.is_superuser && (
                                <button
                                    onClick={() => navigate('/admin')}
                                    className="flex w-full items-center gap-3 px-4 py-3 text-sm text-cyan-400 hover:bg-cyan-500/10 transition-colors border-b border-slate-800/50"
                                >
                                    <Shield className="h-4 w-4" />
                                    <span>Quản trị hệ thống</span>
                                </button>
                            )}
                            
                            {/* Logout */}
                            <button
                                onClick={logout}
                                className="flex w-full items-center gap-3 px-4 py-3 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
                            >
                                <LogOut className="h-4 w-4" />
                                <span>Đăng xuất</span>
                            </button>
                        </div>
                    )}
                    
                    {/* Main Trigger Button */}
                    <button 
                        onClick={() => setIsSettingsOpen(!isSettingsOpen)}
                        className={cn(
                            "flex w-full items-center gap-3 rounded-lg px-4 py-3 text-sm font-medium transition-all duration-200",
                            isSettingsOpen 
                                ? "bg-cyan-500/10 text-cyan-400 shadow-[0_0_15px_-5px_rgba(6,182,212,0.5)]" 
                                : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
                        )}
                    >
                        <Settings className={cn("h-4 w-4 transition-transform duration-500", isSettingsOpen && "rotate-180")} />
                        <span>Cài đặt & Tài khoản</span>
                    </button>
                </div>
            </div>
            
            {/* Modal Layer */}
            <UserProfileDialog isOpen={isProfileOpen} onClose={() => setIsProfileOpen(false)} />

            {/* Main Chat Area */}
            <div className="flex flex-1 flex-col z-10 relative">
                {/* Mobile Header */}
                <header className="flex h-16 items-center border-b border-slate-800 bg-slate-900/40 backdrop-blur-md px-4 md:hidden">
                    <Button variant="ghost" size="icon" className="mr-2 text-slate-400">
                        <Menu className="h-5 w-5" />
                    </Button>
                    <span className="font-bold text-slate-100">Trợ lý AI</span>
                </header>

                {/* Messages Container */}
                <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
                    {messages.map((msg, index) => (
                        <div
                            key={index}
                            className={cn(
                                "flex w-full gap-4 max-w-3xl mx-auto",
                                msg.role === 'user' ? "justify-end" : "justify-start"
                            )}
                        >
                            {msg.role === 'ai' && (
                                <div className="flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-full bg-cyan-900/30 border border-cyan-500/30 text-cyan-400 shadow-[0_0_15px_-3px_rgba(6,182,212,0.4)]">
                                    <Bot className="h-5 w-5" />
                                </div>
                            )}
                            
                            <div
                                className={cn(
                                    "relative px-5 py-3.5 text-sm md:text-base leading-relaxed shadow-lg max-w-[85%] md:max-w-[75%]",
                                    msg.role === 'user' 
                                        ? "bg-gradient-to-br from-blue-600 to-cyan-600 text-white rounded-2xl rounded-tr-sm border border-cyan-400/20" 
                                        : "bg-slate-900/80 backdrop-blur-sm dark:text-slate-100 rounded-2xl rounded-tl-sm border border-slate-700/50"
                                )}
                            >
                                {msg.content}
                            </div>

                            {msg.role === 'user' && (
                                <div className="flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-full bg-blue-600/20 border border-blue-500/30 text-blue-400">
                                    <User className="h-5 w-5" />
                                </div>
                            )}
                        </div>
                    ))}
                    {isTyping && (
                         <div className="flex w-full gap-4 max-w-3xl mx-auto justify-start">
                             <div className="flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-full bg-cyan-900/30 border border-cyan-500/30 text-cyan-400">
                                 <Bot className="h-5 w-5 animate-pulse" />
                             </div>
                             <div className="text-slate-400 text-sm flex items-center">Đang suy nghĩ...</div>
                         </div>
                    )}
                </div>

                {/* Input Area */}
                <div className="p-4 md:p-6 pt-2">
                    <div className="mx-auto max-w-3xl relative">
                        <div className="relative flex items-end gap-2 rounded-xl border border-slate-700/50 bg-slate-900/60 p-2 shadow-2xl backdrop-blur-xl ring-offset-2 focus-within:ring-2 focus-within:ring-cyan-500/50 focus-within:border-cyan-500/50 transition-all duration-300">
                            <Input
                                value={inputValue}
                                onChange={(e) => setInputValue(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                                className="min-h-[44px] w-full resize-none border-0 bg-transparent px-3 py-2.5 text-slate-100 placeholder:text-slate-500 focus-visible:ring-0 focus-visible:ring-offset-0"
                                placeholder="Nhập lệnh hoặc câu hỏi của bạn..."
                            />
                            <Button 
                                onClick={handleSendMessage}
                                size="icon"
                                className="h-10 w-10 shrink-0 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-all shadow-[0_0_10px_-2px_rgba(6,182,212,0.5)] hover:shadow-[0_0_15px_-2px_rgba(6,182,212,0.7)]"
                            >
                                <Send className="h-5 w-5" />
                            </Button>
                        </div>
                        <div className="mt-2 text-center text-xs text-slate-600">
                            AI-ChatBot v2.0 | Hệ thống sẵn sàng
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ChatLayout;
