import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Atom, Lock, User, Cpu, Disc } from 'lucide-react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';

const Login = () => {
    const [isLoading, setIsLoading] = useState(false);
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    
    const navigate = useNavigate();
    const { login, isAuthenticated, user } = useAuth();

    // Redirect if already logged in
    useEffect(() => {
        if (isAuthenticated && user) {
            if (user.is_superuser) {
                navigate('/admin');
            } else {
                navigate('/chat');
            }
        }
    }, [isAuthenticated, user, navigate]);

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setError('');

        try {
            const formData = new FormData();
            formData.append('username', username);
            formData.append('password', password);

            const response = await axios.post('http://localhost:8000/api/v1/auth/login', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });

            const { access_token } = response.data;
            await login(access_token);
            // Redirection handled by useEffect
            
        } catch (err: any) {
            console.error(err);
            setError('Đăng nhập thất bại. Vui lòng kiểm tra lại.');
            setIsLoading(false);
        }
    };

    return (
        <div className="relative flex min-h-screen items-center justify-center bg-slate-950 overflow-hidden font-sans selection:bg-cyan-500/30">
            {/* Background Effects */}
            <div className="absolute inset-0 z-0">
                <div className="absolute top-[-20%] left-[-10%] h-[500px] w-[500px] rounded-full bg-cyan-500/20 blur-[120px] animate-pulse" />
                <div className="absolute bottom-[-20%] right-[-10%] h-[500px] w-[500px] rounded-full bg-blue-600/20 blur-[120px] animate-pulse delay-1000" />
                <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:50px_50px] [mask-image:radial-gradient(ellipse_60%_60%_at_50%_50%,#000_70%,transparent_100%)]" />
            </div>

            <Card className="z-10 w-full max-w-md border-slate-800 bg-slate-900/60 backdrop-blur-xl shadow-2xl relative overflow-hidden group">
                {/* Top Border Gradient */}
                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-cyan-500 to-transparent opacity-50 group-hover:opacity-100 transition-opacity duration-500" />
                
                <CardHeader className="space-y-3 pb-6 text-center">
                    <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-slate-800/50 ring-1 ring-slate-700 shadow-[0_0_20px_-5px_rgba(6,182,212,0.5)] group-hover:shadow-[0_0_30px_-5px_rgba(6,182,212,0.7)] transition-all duration-500">
                        <Atom className="h-8 w-8 text-cyan-400 animate-[spin_10s_linear_infinite]" />
                    </div>
                    <CardTitle className="text-3xl font-bold tracking-tight text-white">
                        <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-500">
                            AI
                        </span>
                        <span className="block text-sm font-normal text-slate-400 mt-2 tracking-widest uppercase">CHAT-BOT</span>
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleLogin} className="space-y-6">
                        <div className="space-y-2 group/input">
                            <label className="text-xs font-medium text-cyan-500/70 ml-1 uppercase tracking-wider">TÀI KHOẢN</label>
                            <div className="relative">
                                <User className="absolute left-3 top-2.5 h-5 w-5 text-slate-500 transition-colors group-focus-within/input:text-cyan-400" />
                                <Input 
                                    type="text" 
                                    placeholder="Nhập tài khoản" 
                                    className="pl-10 bg-slate-950/50 border-slate-800 text-slate-100 placeholder:text-slate-600 focus:border-cyan-500/50 focus:ring-cyan-500/20 transition-all duration-300 hover:border-slate-700 h-10"
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                />
                            </div>
                        </div>
                        <div className="space-y-2 group/input">
                            <label className="text-xs font-medium text-cyan-500/70 ml-1 uppercase tracking-wider">MẬT KHẨU</label>
                            <div className="relative">
                                <Lock className="absolute left-3 top-2.5 h-5 w-5 text-slate-500 transition-colors group-focus-within/input:text-cyan-400" />
                                <Input 
                                    type="password" 
                                    placeholder="Nhập mật khẩu" 
                                    className="pl-10 bg-slate-950/50 border-slate-800 text-slate-100 placeholder:text-slate-600 focus:border-cyan-500/50 focus:ring-cyan-500/20 transition-all duration-300 hover:border-slate-700 h-10"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                />
                            </div>
                        </div>
                        
                        {error && <div className="text-red-500 text-sm text-center">{error}</div>}

                        <div className="pt-2">
                            <Button className="w-full bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-bold tracking-wide h-11 shadow-[0_0_20px_-5px_rgba(6,182,212,0.5)] hover:shadow-[0_0_30px_-5px_rgba(6,182,212,0.8)] border-none transition-all duration-300 group-hover:scale-[1.02]">
                                {isLoading ? (
                                   <div className='flex items-center gap-2'>
                                     <Disc className="h-4 w-4 animate-spin" />
                                     <span>ĐANG XÁC NHẬN...</span>
                                   </div>
                                ) : (
                                    <div className='flex items-center gap-2'>
                                      <Cpu className="h-4 w-4" />
                                      <span>Đăng nhập</span>
                                    </div>
                                )}
                            </Button>
                        </div>
                    </form>
                </CardContent>
            </Card>
        </div>
    );
};

export default Login;
