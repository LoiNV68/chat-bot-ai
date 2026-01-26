import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardTitle, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { FileText, Upload, Trash2, Shield, Activity, Search, Filter, RefreshCw, Eye, MoreVertical, MessageSquare, ArrowLeft, File } from 'lucide-react';
import { cn } from '@/lib/utils';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

interface Document {
    id: number;
    filename: string;
    version: number;
    is_active: boolean;
    created_at: string;
    access_scope: string;
}

const DocumentManager = () => {
    const navigate = useNavigate();
    const [documents, setDocuments] = useState<Document[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [file, setFile] = useState<File | null>(null);

    useEffect(() => {
        fetchDocuments();
    }, []);

    const fetchDocuments = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await axios.get('http://localhost:8000/api/v1/documents/', {
                headers: { Authorization: `Bearer ${token}` }
            });
            setDocuments(response.data);
        } catch (error) {
            console.error(error);
        }
    };

    const handleUpload = async () => {
        if (!file) return;
        setUploading(true);
        try {
            const token = localStorage.getItem('token');
            const formData = new FormData();
            formData.append('file', file);
            formData.append('scope', 'public'); // Default for now

            await axios.post('http://localhost:8000/api/v1/documents/upload', formData, {
                headers: { 
                    Authorization: `Bearer ${token}`,
                    'Content-Type': 'multipart/form-data'
                }
            });
            
            setFile(null);
            fetchDocuments(); // Refresh list via API
        } catch (error) {
            console.error('Upload failed', error);
        } finally {
            setUploading(false);
        }
    };

    return (
        <div className="relative min-h-screen overflow-hidden bg-slate-950 font-sans text-slate-100 selection:bg-cyan-500/30">
            {/* Background Effects (Consistent with Login/Chat) */}
            <div className="absolute inset-0 z-0 pointer-events-none">
                <div className="absolute top-[-20%] left-[-10%] h-[500px] w-[500px] rounded-full bg-cyan-500/10 blur-[120px] animate-pulse" />
                <div className="absolute bottom-[-20%] right-[-10%] h-[500px] w-[500px] rounded-full bg-blue-600/10 blur-[120px] animate-pulse delay-1000" />
                <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:40px_40px] [mask-image:radial-gradient(ellipse_80%_80%_at_50%_50%,#000_70%,transparent_100%)]" />
            </div>

            <div className="relative z-10 container mx-auto p-8 space-y-8">
                
                {/* Header Section */}
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="space-y-1">
                        <div className="flex items-center gap-3">
                            <Button 
                                variant="ghost" 
                                size="icon" 
                                onClick={() => navigate('/chat')}
                                className="h-8 w-8 text-slate-400 hover:text-cyan-400 hover:bg-cyan-500/10 rounded-full"
                            >
                                <ArrowLeft className="h-5 w-5" />
                            </Button>
                            <h1 className="text-3xl font-bold text-white tracking-tight flex items-center gap-3">
                                <Shield className="h-8 w-8 text-cyan-500" />
                                Quản trị Tài liệu
                            </h1>
                        </div>
                        <p className="text-slate-400 ml-11">Quản lý, tải lên và phân quyền truy cập tài liệu cho Chatbot.</p>
                    </div>
                </div>
                
                {/* Upload Section */}
                <Card className="border-cyan-500/20 bg-slate-900/60 backdrop-blur-xl shadow-lg relative overflow-hidden group">
                     {/* Decorative top line */}
                     <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-cyan-500/50 to-transparent" />
                    <CardHeader>
                        <CardTitle className="text-xl text-slate-100 flex items-center gap-2">
                           <Upload className="h-5 w-5 text-cyan-400" />
                           Tải lên tài liệu mới
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="flex flex-col md:flex-row gap-4 items-center">
                        <div className="relative w-full">
                            <Input 
                                type="file" 
                                onChange={(e) => setFile(e.target.files?.[0] || null)}
                                className="bg-slate-950/50 border-slate-700 text-slate-300 file:bg-slate-800 file:text-cyan-400 file:border-0 file:mr-4 file:py-2 file:px-4 file:rounded-md hover:file:bg-slate-700 transition-all cursor-pointer"
                            />
                        </div>
                        <Button 
                            onClick={handleUpload}
                            disabled={uploading || !file}
                            className="w-full md:w-auto bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-medium shadow-[0_0_15px_-3px_rgba(6,182,212,0.5)] border-0"
                        >
                            <Upload className="mr-2 h-4 w-4" /> 
                            {uploading ? 'Đang tải...' : 'Tải lên'}
                        </Button>
                    </CardContent>
                </Card>

                {/* Main Content Area */}
                <Card className="border-slate-800 bg-slate-900/60 backdrop-blur-xl shadow-xl">
                    <CardHeader className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-slate-800/50 pb-6">
                        <CardTitle className="text-xl text-slate-100 flex items-center gap-2">
                            <FileText className="h-5 w-5 text-blue-400" />
                            Danh sách tài liệu hiện có
                        </CardTitle>
                        
                         {/* Search & Filter Toolbar */}
                        <div className="flex gap-2 w-full md:w-auto">
                            <div className="relative group/search flex-1 md:w-64">
                                <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500 group-focus-within/search:text-cyan-400 transition-colors" />
                                <Input 
                                    placeholder="Tìm kiếm tài liệu..." 
                                    className="pl-9 bg-slate-950/50 border-slate-800 text-slate-200 focus:border-cyan-500/50 focus:ring-cyan-500/20 h-9"
                                />
                            </div>
                            <Button variant="outline" size="icon" className="border-slate-800 bg-slate-950/30 text-slate-400 hover:text-cyan-400 hover:border-cyan-500/30 hover:bg-cyan-500/10">
                                <Filter className="h-4 w-4" />
                            </Button>
                        </div>
                    </CardHeader>
                    <CardContent className="p-0">
                        <div className="overflow-x-auto">
                            <table className="w-full text-left border-collapse">
                                <thead>
                                    <tr className="border-b border-slate-800 bg-slate-950/30 text-xs uppercase tracking-wider text-slate-500 font-semibold">
                                        <th className="p-4">Tên tập tin</th>
                                        <th className="p-4">Phiên bản</th>
                                        <th className="p-4">Trạng thái</th>
                                        <th className="p-4 text-right">Hành động</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-800/50">
                                    {documents.length === 0 ? (
                                        <tr>
                                            <td colSpan={4} className="p-8 text-center text-slate-500">
                                                Chưa có tài liệu nào.
                                            </td>
                                        </tr>
                                    ) : (
                                        documents.map((doc, i) => (
                                        <tr key={doc.id} className="group hover:bg-cyan-500/5 transition-colors duration-200">
                                            <td className="p-4 font-medium text-slate-200 flex items-center gap-3">
                                                <div className="p-2 rounded bg-slate-800/50 text-cyan-400 group-hover:text-cyan-300 group-hover:bg-cyan-500/20 transition-all">
                                                    <FileText className="h-4 w-4" />
                                                </div>
                                                {doc.filename}
                                            </td>
                                            <td className="p-4 text-slate-400 font-mono text-sm">v{doc.version}</td>
                                            <td className="p-4">
                                                <span className={cn(
                                                    "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border",
                                                    doc.is_active 
                                                        ? "bg-green-500/10 text-green-400 border-green-500/20" 
                                                        : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                                                )}>
                                                    <Activity className="h-3 w-3" />
                                                    {doc.is_active ? 'Hoạt động' : 'Đã lưu trữ'}
                                                </span>
                                            </td>
                                            <td className="p-4 text-right">
                                                <Button 
                                                    size="sm" 
                                                    variant="ghost" 
                                                    className="text-slate-400 hover:text-red-400 hover:bg-red-500/10 opacity-70 group-hover:opacity-100 transition-all"
                                                >
                                                    <Trash2 className="h-4 w-4 mr-1" />
                                                    Xóa
                                                </Button>
                                            </td>
                                        </tr>
                                    )))}
                                </tbody>
                            </table>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
};

export default DocumentManager;
