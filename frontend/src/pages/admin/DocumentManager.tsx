import { Button } from '@/components/ui/button';
import { Card, CardContent, CardTitle, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { FileText, Upload, Trash2, Shield, Activity, Search, Filter, ArrowLeft, Clock, User, RotateCcw, Eye, Download } from 'lucide-react';
import { cn } from '@/lib/utils';
import axios from 'axios';
import { API_ENDPOINTS } from '@/config/api';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { useState, useEffect, useRef } from 'react';
import ConfirmModal from '@/components/ConfirmModal';

interface Document {
    id: number;
    filename: string;
    version: number;
    is_active: boolean;
    is_processed: boolean;
    created_at: string;
    access_scope: string;
    uploader?: {
        full_name: string;
    };
}

const DocumentManager = () => {
    const navigate = useNavigate();
    const { } = useAuth();
    const [documents, setDocuments] = useState<Document[]>([]);
    const [isDocsLoading, setIsDocsLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [file, setFile] = useState<File | null>(null);
    const [viewMode, setViewMode] = useState<'active' | 'trash'>('active');
    const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
    const [selectedDocId, setSelectedDocId] = useState<number | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const [alertModal, setAlertModal] = useState<{
        isOpen: boolean;
        title: string;
        message: string;
        type: 'danger' | 'info' | 'warning';
    }>({
        isOpen: false,
        title: '',
        message: '',
        type: 'info'
    });

    // Lấy tài liệu khi viewMode thay đổi
    useEffect(() => {
        fetchDocuments();
    }, [viewMode]);

    // Tự động poll khi có tài liệu đang được xử lý
    useEffect(() => {
        const hasProcessingDocs = documents.some(doc => !doc.is_processed);
        
        if (hasProcessingDocs && viewMode === 'active') {
            const pollInterval = setInterval(() => {
                fetchDocuments();
            }, 10000); // Poll mỗi 10 giây
            
            return () => clearInterval(pollInterval);
        }
    }, [documents, viewMode]);

    const fetchDocuments = async () => {
        setIsDocsLoading(true);
        try {
            const token = localStorage.getItem('token');
            const endpoint = viewMode === 'active' 
                ? API_ENDPOINTS.DOCUMENTS.BASE 
                : API_ENDPOINTS.DOCUMENTS.TRASH;
            
            const response = await axios.get(endpoint, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setDocuments(response.data);
        } catch (error) {
            console.error(error);
        } finally {
            setIsDocsLoading(false);
        }
    };

    const handleUpload = async () => {
        if (!file) return;
        setUploading(true);
        try {
            const token = localStorage.getItem('token');
            const formData = new FormData();
            formData.append('file', file);
            formData.append('scope', 'public');

            await axios.post(API_ENDPOINTS.DOCUMENTS.UPLOAD, formData, {
                headers: { 
                    Authorization: `Bearer ${token}`,
                    'Content-Type': 'multipart/form-data'
                }
            });
            
            setFile(null);
            if (fileInputRef.current) {
                fileInputRef.current.value = '';
            }
            if (viewMode === 'active') fetchDocuments();
        } catch (error: any) {
            if (error?.response?.status === 409) {
                setAlertModal({
                    isOpen: true,
                    title: 'Thông báo',
                    message: error.response.data.detail || 'Đang có tài liệu đang xử lý. Vui lòng đợi.',
                    type: 'warning'
                });
                fetchDocuments(); // Refresh lại danh sách
            } else {
                console.error('Upload failed', error);
                setAlertModal({
                    isOpen: true,
                    title: 'Lỗi tải lên',
                    message: 'Tải lên thất bại. Vui lòng thử lại.',
                    type: 'danger'
                });
            }
        } finally {
            setUploading(false);
        }
    };

    const handleDeleteClick = (id: number) => {
        setSelectedDocId(id);
        setIsDeleteModalOpen(true);
    };

    const confirmDelete = async () => {
        if (!selectedDocId) return;
        try {
            const token = localStorage.getItem('token');
            await axios.delete(API_ENDPOINTS.DOCUMENTS.BY_ID(selectedDocId), {
                headers: { Authorization: `Bearer ${token}` }
            });
            fetchDocuments();
        } catch (error) {
            console.error('Delete failed', error);
        } finally {
            setIsDeleteModalOpen(false);
            setSelectedDocId(null);
        }
    };

    const handleRestore = async (id: number) => {
        try {
            const token = localStorage.getItem('token');
            await axios.post(API_ENDPOINTS.DOCUMENTS.RESTORE(id), null, {
                headers: { Authorization: `Bearer ${token}` }
            });
            fetchDocuments();
        } catch (error) {
            console.error('Restore failed', error);
        }
    };

    const handlePreview = async (id: number, filename: string) => {
        try {
            const token = localStorage.getItem('token');
            const isPdf = filename.toLowerCase().endsWith('.pdf');
            
            const response = await axios.get(API_ENDPOINTS.DOCUMENTS.CONTENT(id), {
                headers: { Authorization: `Bearer ${token}` },
                responseType: 'blob'
            });
            
            const blob = new Blob([response.data], { 
                type: isPdf ? 'application/pdf' : 'application/octet-stream' 
            });
            const url = window.URL.createObjectURL(blob);
            
            if (isPdf) {
                window.open(url, '_blank');
            } else {
                const link = document.createElement('a');
                link.href = url;
                link.setAttribute('download', filename);
                document.body.appendChild(link);
                link.click();
                link.parentNode?.removeChild(link);
            }
            
            setTimeout(() => window.URL.revokeObjectURL(url), 100);
            
        } catch (error) {
            console.error('Preview failed', error);
            alert('Không thể tải file này.');
        }
    };

    return (
        <div className="relative min-h-screen overflow-hidden bg-slate-950 font-sans text-slate-100 selection:bg-cyan-500/30">
            {/* Hiệu ứng nền */}
            <div className="absolute inset-0 z-0 pointer-events-none">
                <div className="absolute top-[-20%] left-[-10%] h-[500px] w-[500px] rounded-full bg-cyan-500/10 blur-[120px] animate-pulse" />
                <div className="absolute bottom-[-20%] right-[-10%] h-[500px] w-[500px] rounded-full bg-blue-600/10 blur-[120px] animate-pulse delay-1000" />
                <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:40px_40px] [mask-image:radial-gradient(ellipse_80%_80%_at_50%_50%,#000_70%,transparent_100%)]" />
            </div>

            <div className="relative z-10 container mx-auto p-4 md:p-8 space-y-8">
                
                {/* Phần Header */}
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
                                Quản trị Hệ Thống
                            </h1>
                        </div>
                        <p className="text-slate-400 ml-11">Quản lý tài liệu và theo dõi hoạt động của hệ thống Chatbot.</p>
                    </div>
                    
                    <div className="flex gap-2">
                        <Button
                            variant={viewMode === 'active' ? 'default' : 'outline'}
                            onClick={() => setViewMode('active')}
                            className={viewMode === 'active' ? "bg-cyan-600 hover:bg-cyan-700 text-white" : "border-slate-700 text-slate-400 hover:text-cyan-400"}
                        >
                            <FileText className="h-4 w-4 mr-2" />
                            Tài liệu
                        </Button>
                        <Button
                            variant={viewMode === 'trash' ? 'destructive' : 'outline'}
                            onClick={() => setViewMode('trash')}
                            className={viewMode === 'trash' ? "bg-red-900/50 hover:bg-red-900/70 border-red-500/50 text-red-100" : "border-slate-700 text-slate-400 hover:text-red-400"}
                        >
                            <Trash2 className="h-4 w-4 mr-2" />
                            Thùng rác
                        </Button>
                    </div>
                </div>
                
                <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-300">
                    {viewMode === 'active' && (
                        <Card className={cn(
                            "border-cyan-500/20 bg-slate-900/60 backdrop-blur-xl shadow-lg relative overflow-hidden group",
                            documents.some(doc => !doc.is_processed) && "opacity-60"
                        )}>
                            <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-cyan-500/50 to-transparent" />
                            <CardHeader>
                                <CardTitle className="text-xl text-slate-100 flex items-center gap-2">
                                   <Upload className="h-5 w-5 text-cyan-400" />
                                   Tải lên tài liệu mới
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                {documents.some(doc => !doc.is_processed) && (
                                    <div className="flex items-center gap-2 px-4 py-2.5 rounded-md bg-amber-500/10 border border-amber-500/30 text-amber-300 text-sm">
                                        <Activity className="h-4 w-4 animate-pulse flex-shrink-0" />
                                        <span>Đang có tài liệu đang xử lý. Vui lòng đợi hoàn tất trước khi tải lên tài liệu mới.</span>
                                    </div>
                                )}
                                <div className="flex flex-col md:flex-row gap-4 items-center">
                                    <div className="relative w-full">
                                        <input 
                                            ref={fileInputRef}
                                            type="file" 
                                            onChange={(e) => setFile(e.target.files?.[0] || null)}
                                            className="hidden" 
                                            id="file-upload"
                                            disabled={documents.some(doc => !doc.is_processed)}
                                        />
                                        <label 
                                            htmlFor="file-upload"
                                            className={cn(
                                                "flex items-center w-full px-4 py-2 bg-slate-950/50 border border-slate-700 rounded-md text-slate-300 transition-colors group/input",
                                                documents.some(doc => !doc.is_processed) 
                                                    ? "cursor-not-allowed opacity-50" 
                                                    : "cursor-pointer hover:bg-slate-900"
                                            )}
                                        >
                                            <span className="bg-slate-800 text-cyan-400 px-3 py-1 rounded text-sm mr-3 border border-slate-700 group-hover/input:bg-slate-700 transition-colors">
                                                Chọn tệp...
                                            </span>
                                            <span className="text-sm text-slate-400 truncate">
                                                {file ? file.name : 'Chưa chọn tệp nào'}
                                            </span>
                                        </label>
                                    </div>
                                    <Button 
                                        onClick={handleUpload}
                                        disabled={uploading || !file || documents.some(doc => !doc.is_processed)}
                                        className="w-full md:w-auto bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-medium shadow-[0_0_15px_-3px_rgba(6,182,212,0.5)] border-0 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        <Upload className="mr-2 h-4 w-4" /> 
                                        {uploading ? 'Đang tải...' : 'Tải lên'}
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    <Card className="border-slate-800 bg-slate-900/60 backdrop-blur-xl shadow-xl">
                        <CardHeader className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-slate-800/50 pb-6">
                            <CardTitle className="text-xl text-slate-100 flex items-center gap-2">
                                {viewMode === 'active' ? (
                                    <>
                                        <FileText className="h-5 w-5 text-blue-400" />
                                        Danh sách tài liệu hiện có
                                    </>
                                ) : (
                                    <>
                                        <Trash2 className="h-5 w-5 text-red-500" />
                                        Thùng rác - Tài liệu đã xóa
                                    </>
                                )}
                            </CardTitle>
                            
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
                                            <th className="p-4">Ngày tạo</th>
                                            <th className="p-4">Người tạo</th>
                                            <th className="p-4">Trạng thái</th>
                                            <th className="p-4 text-right">Hành động</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-800/50">
                                        {isDocsLoading ? (
                                            <tr>
                                                <td colSpan={5} className="p-8 text-center text-slate-500">
                                                    <Activity className="h-8 w-8 animate-spin mx-auto mb-2 opacity-50" />
                                                    Đang tải dữ liệu...
                                                </td>
                                            </tr>
                                        ) : documents.length === 0 ? (
                                            <tr>
                                                <td colSpan={5} className="p-8 text-center text-slate-500">
                                                    {viewMode === 'active' ? 'Chưa có tài liệu nào.' : 'Thùng rác trống.'}
                                                </td>
                                            </tr>
                                        ) : (
                                            documents.map((doc) => (
                                            <tr key={doc.id} className="group hover:bg-cyan-500/5 transition-colors duration-200">
                                                <td className="p-4 font-medium text-slate-200 flex items-center gap-3">
                                                    <div className="p-2 rounded bg-slate-800/50 text-cyan-400 group-hover:text-cyan-300 group-hover:bg-cyan-500/20 transition-all">
                                                        <FileText className="h-4 w-4" />
                                                    </div>
                                                    {doc.filename}
                                                </td>
                                                <td className="p-4 text-slate-400 text-sm">
                                                    <div className="flex items-center gap-2">
                                                        <Clock className="h-3 w-3" />
                                                        {new Date(doc.created_at).toLocaleDateString('vi-VN')}
                                                    </div>
                                                </td>
                                                <td className="p-4 text-slate-300 text-sm">
                                                    <div className="flex items-center gap-2">
                                                        <User className="h-3 w-3 text-cyan-500/70" />
                                                        {doc.uploader?.full_name || 'Hệ thống'}
                                                    </div>
                                                </td>
                                                <td className="p-4">
                                                    <span className={cn(
                                                        "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border",
                                                        doc.is_processed 
                                                            ? "bg-green-500/10 text-green-400 border-green-500/20" 
                                                            : "bg-yellow-500/10 text-yellow-400 border-yellow-500/20"
                                                    )}>
                                                        <Activity className="h-3 w-3" />
                                                        {doc.is_processed ? 'Đã xử lý' : 'Đang xử lý'}
                                                    </span>
                                                </td>
                                                <td className="p-4 text-right">
                                                    {viewMode === 'active' ? (
                                                        <div className="flex justify-end gap-1">
                                                            <Button
                                                                size="sm"
                                                                variant="ghost"
                                                                onClick={() => handlePreview(doc.id, doc.filename)}
                                                                className="text-slate-400 hover:text-cyan-400 hover:bg-cyan-500/10 opacity-70 group-hover:opacity-100 transition-all"
                                                                title={doc.filename.endsWith('.pdf') ? "Xem trước" : "Tải xuống"}
                                                            >
                                                                {doc.filename.endsWith('.pdf') ? <Eye className="h-4 w-4" /> : <Download className="h-4 w-4" />}
                                                            </Button>
                                                            <Button 
                                                                size="sm" 
                                                                variant="ghost" 
                                                                onClick={() => handleDeleteClick(doc.id)}
                                                                className="text-slate-400 hover:text-red-400 hover:bg-red-500/10 opacity-70 group-hover:opacity-100 transition-all"
                                                                title="Xóa"
                                                            >
                                                                <Trash2 className="h-4 w-4" />
                                                            </Button>
                                                        </div>
                                                    ) : (
                                                        <Button 
                                                            size="sm" 
                                                            variant="ghost" 
                                                            onClick={() => handleRestore(doc.id)}
                                                            className="text-slate-400 hover:text-green-400 hover:bg-green-500/10 opacity-70 group-hover:opacity-100 transition-all"
                                                        >
                                                            <RotateCcw className="h-4 w-4 mr-1" />
                                                            Khôi phục
                                                        </Button>
                                                    )}
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

            <ConfirmModal 
                isOpen={isDeleteModalOpen}
                title="Xóa tài liệu?"
                message="Bạn có chắc chắn muốn xóa tài liệu này? Hành động này sẽ chuyển tài liệu vào thùng rác."
                confirmText="Xóa ngay"
                cancelText="Quay lại"
                onConfirm={confirmDelete}
                onCancel={() => setIsDeleteModalOpen(false)}
            />

            <ConfirmModal 
                isOpen={alertModal.isOpen}
                title={alertModal.title}
                message={alertModal.message}
                confirmText="Đóng"
                showCancel={false}
                type={alertModal.type}
                onConfirm={() => setAlertModal(prev => ({ ...prev, isOpen: false }))}
                onCancel={() => setAlertModal(prev => ({ ...prev, isOpen: false }))}
            />
        </div>
    );
};

export default DocumentManager;
