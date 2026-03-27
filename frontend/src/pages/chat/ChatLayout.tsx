import React, { useState, useEffect } from "react";
import {
  Send,
  Bot,
  User,
  Plus,
  MessageSquare,
  Settings,
  Menu,
  LogOut,
  Shield,
  Loader2,
  PanelLeftClose,
  PanelLeftOpen,
  X,
  MoreHorizontal,
  Pin,
  PinOff,
  Pencil,
  Trash,
  FileText,
  Download,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import axios from "axios";
import { API_ENDPOINTS } from "@/config/api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
// @ts-ignore 
import remarkBreaks from "remark-breaks";
import { useAuth } from "@/context/AuthContext";
import { useNavigate } from "react-router-dom";
import UserProfileDialog from "@/components/UserProfileDialog";
import ConfirmModal from "@/components/ConfirmModal";
import RenameModal from "@/components/RenameModal";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface ChatSession {
  id: string;
  title: string | null;
  is_pinned: boolean;
  updated_at: string;
}

interface SourceDocument {
  doc_id: number;
  filename: string;
  score: number;
}

interface ChatMessage {
  role: string;
  content: string;
  sources?: SourceDocument[];
  has_related_docs?: boolean;
}

interface SidebarContentProps {
  isCollapsed: boolean;
  toggleSidebar: () => void;
  setIsMobileMenuOpen: (value: boolean) => void;
  handleNewChat: () => void;
  sessions: ChatSession[];
  currentSessionId: string | null;
  loadSession: (id: string) => void;
  handleRenameSession: (e: React.MouseEvent, id: string) => void;
  handlePinSession: (e: React.MouseEvent, session: ChatSession) => void;
  handleDeleteSession: (e: React.MouseEvent, id: string) => void;
  isSettingsOpen: boolean;
  setIsSettingsOpen: (value: boolean) => void;
  setIsProfileOpen: (value: boolean) => void;
  user: any;
  navigate: any;
  logout: any;
}

const normalizeMarkdownSpacing = (content: string): string => {
  return content
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .replace(/\u00A0/g, " ")
    .split("\n")
    .map((line) => line.replace(/[ \t]+$/g, ""))
    .join("\n")
    // Remove empty bullet/number markers that create giant visual gaps.
    .replace(/^\s*[-*+]\s*$/gm, "")
    .replace(/^\s*\d+\.\s*$/gm, "")
    // Collapse excessive blank lines globally.
    .replace(/\n{3,}/g, "\n\n")
    // Keep list items compact: avoid double blank lines between items.
    .replace(
      /(\n\s*(?:[-*+]\s+.+|\d+\.\s+.+))\n{2,}(?=\s*(?:[-*+]\s+|\d+\.\s+))/g,
      "$1\n",
    )
    .trim();
};

const formatAssistantContent = (content: string): string => {
  if (!content) return "";

  const normalized = normalizeMarkdownSpacing(content);
  if (!normalized) return "";

  const hasMarkdownStructure =
    /(^|\n)\s*([-*+]\s+|\d+\.\s+|#{1,6}\s+|\|)/.test(normalized) ||
    /`{3}|`[^`]+`|\*\*[^*]+\*\*/.test(normalized) ||
    normalized.includes("\n");

  if (hasMarkdownStructure) return normalized;
  if (normalized.length <= 220) return normalized;

  const sentences = normalized
    .split(/(?<=[.!?])\s+(?=\S)/g)
    .map((s) => s.trim())
    .filter(Boolean);

  if (sentences.length < 3) return normalized;

  const paragraphs: string[] = [];
  for (let i = 0; i < sentences.length; i += 2) {
    paragraphs.push(sentences.slice(i, i + 2).join(" "));
  }

  return paragraphs.join("\n\n");
};

const SidebarContent = ({
  isCollapsed,
  toggleSidebar,
  setIsMobileMenuOpen,
  handleNewChat,
  sessions,
  currentSessionId,
  loadSession,
  handleRenameSession,
  handlePinSession,
  handleDeleteSession,
  isSettingsOpen,
  setIsSettingsOpen,
  setIsProfileOpen,
  user,
  navigate,
  logout,
}: SidebarContentProps) => {
  const menuRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsSettingsOpen(false);
      }
    };
    if (isSettingsOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isSettingsOpen, setIsSettingsOpen]);

  return (
    <>
      <div
        className={cn(
          "flex h-16 items-center border-b border-slate-800",
          isCollapsed ? "justify-center px-0" : "px-6 justify-between",
        )}
      >
        {!isCollapsed && (
          <span className="text-lg font-bold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-500 animate-in fade-in duration-300">
            AI CHAT-BOT
          </span>
        )}
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleSidebar}
          className={cn(
            "hidden md:flex text-slate-400 hover:text-cyan-400 hover:bg-cyan-500/10",
            isCollapsed && "mx-auto",
          )}
        >
          {isCollapsed ? (
            <PanelLeftOpen className="h-5 w-5" />
          ) : (
            <PanelLeftClose className="h-5 w-5" />
          )}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setIsMobileMenuOpen(false)}
          className="flex md:hidden text-slate-400 hover:text-red-400"
        >
          <X className="h-5 w-5" />
        </Button>
      </div>

      <div className="p-4">
        <Button
          onClick={handleNewChat}
          className={cn(
            "w-full bg-gradient-to-r from-cyan-600/20 to-blue-600/20 border border-cyan-500/30 text-cyan-400 hover:text-cyan-300 hover:border-cyan-400 hover:bg-cyan-500/10 transition-all font-medium",
            isCollapsed ? "justify-center px-0" : "justify-start gap-2",
          )}
          title="Cuộc trò chuyện mới"
        >
          <Plus className="h-4 w-4" />
          {!isCollapsed && <span>CUỘC TRÒ CHUYỆN MỚI</span>}
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-2">
        {!isCollapsed && (
          <h3 className="mb-2 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500 animate-in fade-in">
            NHẬT KÝ GẦN ĐÂY
          </h3>
        )}
        <div className="space-y-1">
          {sessions.map((session) => (
            <div
              key={session.id}
              className={cn(
                "group flex items-center gap-3 rounded-lg py-3 text-sm transition-all hover:bg-white/5 cursor-pointer relative",
                currentSessionId === session.id
                  ? "bg-white/10 text-cyan-300"
                  : "text-slate-400",
                isCollapsed ? "justify-center px-0" : "px-4",
              )}
              onClick={() => loadSession(session.id)}
              title={session.title || "New Chat"}
            >
              <MessageSquare className="h-4 w-4 opacity-70 shrink-0" />
              {!isCollapsed && (
                <>
                  <span className="truncate flex-1">
                    {session.title || "New Chat"}
                  </span>
                  {session.is_pinned && (
                    <Pin className="h-3 w-3 text-cyan-500 shrink-0" />
                  )}

                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-slate-700 p-0"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent
                      align="end"
                      className="w-48 bg-slate-900 border-slate-700 text-slate-200"
                    >
                      <DropdownMenuItem
                        onClick={(e) => handleRenameSession(e, session.id)}
                        className="cursor-pointer hover:bg-slate-800 focus:bg-slate-800"
                      >
                        <Pencil className="mr-2 h-4 w-4" /> Đổi tên
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={(e) => handlePinSession(e, session)}
                        className="cursor-pointer hover:bg-slate-800 focus:bg-slate-800"
                      >
                        {session.is_pinned ? (
                          <>
                            <PinOff className="mr-2 h-4 w-4" /> Bỏ ghim
                          </>
                        ) : (
                          <>
                            <Pin className="mr-2 h-4 w-4" /> Ghim hội thoại
                          </>
                        )}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={(e) => handleDeleteSession(e, session.id)}
                        className="cursor-pointer text-red-400 hover:text-red-300 hover:bg-red-500/10 focus:bg-red-500/10"
                      >
                        <Trash className="mr-2 h-4 w-4" /> Xóa hội thoại
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </>
              )}
            </div>
          ))}
        </div>
      </div>

      <div ref={menuRef} className="border-t border-slate-800 p-4 relative">
        {isSettingsOpen && !isCollapsed && (
          <div className="absolute bottom-full left-4 right-4 mb-2 rounded-xl border border-slate-700 bg-slate-900/95 backdrop-blur-xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200 z-50">
            <button
              onClick={() => setIsProfileOpen(true)}
              className="flex w-full items-center gap-3 px-4 py-3 text-sm text-slate-200 hover:bg-slate-800 transition-colors border-b border-slate-800/50"
            >
              <User className="h-4 w-4 text-slate-400" />
              <span>Thông tin cá nhân</span>
            </button>
            {/* Document Management: Admin or Lecturer */}
            {(user?.is_superuser ||
              user?.role === "lecturer" ||
              user?.role === "admin") && (
                <button
                  onClick={() => navigate("/admin")}
                  className="flex w-full items-center gap-3 px-4 py-3 text-sm text-cyan-400 hover:bg-cyan-500/10 transition-colors border-b border-slate-800/50"
                >
                  <Shield className="h-4 w-4" />
                  <span>Quản lý tài liệu</span>
                </button>
              )}
            {/* User Management: Admin only */}
            {user?.is_superuser && (
              <button
                onClick={() => navigate("/admin/users")}
                className="flex w-full items-center gap-3 px-4 py-3 text-sm text-purple-400 hover:bg-purple-500/10 transition-colors border-b border-slate-800/50"
              >
                <Shield className="h-4 w-4" />
                <span>Quản lý người dùng</span>
              </button>
            )}
            <button
              onClick={logout}
              className="flex w-full items-center gap-3 px-4 py-3 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
            >
              <LogOut className="h-4 w-4" />
              <span>Đăng xuất</span>
            </button>
          </div>
        )}

        <button
          onClick={() => !isCollapsed && setIsSettingsOpen(!isSettingsOpen)}
          className={cn(
            "flex w-full items-center gap-3 rounded-lg py-3 text-sm font-medium transition-all duration-200",
            isSettingsOpen && !isCollapsed
              ? "bg-cyan-500/10 text-cyan-400 shadow-[0_0_15px_-5px_rgba(6,182,212,0.5)]"
              : "text-slate-400 hover:bg-white/5 hover:text-slate-200",
            isCollapsed ? "justify-center px-0" : "px-4",
          )}
        >
          <Settings
            className={cn(
              "h-4 w-4 transition-transform duration-500",
              isSettingsOpen && !isCollapsed && "rotate-180",
            )}
          />
          {!isCollapsed && <span>Cài đặt & Tài khoản</span>}
        </button>
      </div>
    </>
  );
};

const ChatLayout = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [lastMessageTime, setLastMessageTime] = useState(0);
  const COOLDOWN_MS = 2000;
  const chatContainerRef = React.useRef<HTMLDivElement>(null);
  const chatContextRef = React.useRef<number>(0);

  const scrollToBottom = () => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping, currentSessionId]);

  useEffect(() => {
    fetchSessions();
  }, []);

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth >= 768) setIsMobileMenuOpen(false);
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const fetchSessions = async () => {
    try {
      const token = localStorage.getItem("token");
      const response = await axios.get(API_ENDPOINTS.CHAT.SESSIONS, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setSessions(response.data);
    } catch (error) {
      console.error("Failed to fetch sessions:", error);
    }
  };

  const loadSession = async (sessionId: string) => {
    try {
      chatContextRef.current += 1;
      setIsTyping(false);

      setCurrentSessionId(sessionId);
      const token = localStorage.getItem("token");
      const response = await axios.get(API_ENDPOINTS.CHAT.MESSAGES(sessionId), {
        headers: { Authorization: `Bearer ${token}` },
      });
      setMessages(response.data);
      if (window.innerWidth < 768) setIsMobileMenuOpen(false);
    } catch (error) {
      console.error("Failed to load session:", error);
    }
  };

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;

    const now = Date.now();
    if (now - lastMessageTime < COOLDOWN_MS) {
      setMessages((prev) => [
        ...prev,
        {
          role: "ai",
          content: "⏳ Bạn đang thao tác quá nhanh. Vui lòng đợi 2 giây.",
        },
      ]);
      return;
    }

    const currentContext = chatContextRef.current;

    const newMessages = [...messages, { role: "user", content: inputValue }];
    setMessages(newMessages);
    setInputValue("");
    setIsTyping(true);
    setLastMessageTime(now);

    try {
      const token = localStorage.getItem("token");
      const response = await axios.post(
        API_ENDPOINTS.CHAT.COMPLETION,
        {
          query: inputValue,
          session_id: currentSessionId,
          history: [],
        },
        { headers: { Authorization: `Bearer ${token}` } },
      );

      // Optionally refresh sidebar if it might be a new session
      if (!currentSessionId) fetchSessions();

      if (chatContextRef.current !== currentContext) return;

      if (!currentSessionId && response.data.session_id) {
        setCurrentSessionId(response.data.session_id);
      }

      setMessages((prev) => [
        ...prev,
        {
          role: "ai",
          content: response.data.answer,
          sources: response.data.sources || [],
          has_related_docs: response.data.has_related_docs || false,
        },
      ]);
    } catch (error: any) {
      console.error("Chat error:", error);
      if (chatContextRef.current === currentContext) {
        setMessages((prev) => [
          ...prev,
          { role: "ai", content: "Xin lỗi, hệ thống đang gặp sự cố." },
        ]);
      }
    } finally {
      if (chatContextRef.current === currentContext) {
        setIsTyping(false);
      }
    }
  };

  const handleNewChat = () => {
    chatContextRef.current += 1;
    setCurrentSessionId(null);
    setMessages([]);
    setInputValue("");
    setIsTyping(false);
    if (window.innerWidth < 768) setIsMobileMenuOpen(false);
  };

  const toggleSidebar = () => setIsCollapsed(!isCollapsed);

  const handlePinSession = async (
    e: React.MouseEvent,
    session: ChatSession,
  ) => {
    e.stopPropagation();
    try {
      const token = localStorage.getItem("token");
      await axios.patch(
        API_ENDPOINTS.CHAT.SESSION(session.id),
        { is_pinned: !session.is_pinned },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      fetchSessions();
    } catch (error) {
      console.error("Failed to pin session:", error);
    }
  };

  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(
    null,
  );
  const [selectedSessionTitle, setSelectedSessionTitle] = useState("");

  const handleDeleteSession = async (
    e: React.MouseEvent,
    sessionId: string,
  ) => {
    e.stopPropagation();
    setSelectedSessionId(sessionId);
    setIsDeleteModalOpen(true);
  };

  const confirmDeleteSession = async () => {
    if (!selectedSessionId) return;
    try {
      const token = localStorage.getItem("token");
      await axios.delete(API_ENDPOINTS.CHAT.SESSION(selectedSessionId), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (currentSessionId === selectedSessionId) handleNewChat();
      fetchSessions();
    } catch (error) {
      console.error("Failed to delete session:", error);
    } finally {
      setIsDeleteModalOpen(false);
      setSelectedSessionId(null);
    }
  };

  const handleRenameSession = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    const session = sessions.find((s) => s.id === sessionId);
    if (session) {
      setSelectedSessionId(sessionId);
      setSelectedSessionTitle(session.title || "");
      setIsRenameModalOpen(true);
    }
  };

  const confirmRenameSession = async (newTitle: string) => {
    if (!selectedSessionId) return;
    try {
      const token = localStorage.getItem("token");
      await axios.patch(
        API_ENDPOINTS.CHAT.SESSION(selectedSessionId),
        { title: newTitle },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      fetchSessions();
    } catch (error) {
      console.error("Failed to rename session:", error);
    }
  };

  return (
    <div className="relative flex h-screen overflow-hidden bg-slate-950 font-sans text-slate-100 selection:bg-cyan-500/30">
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute top-[-20%] left-[-10%] h-[500px] w-[500px] rounded-full bg-cyan-500/10 blur-[120px] animate-pulse" />
        <div className="absolute bottom-[-20%] right-[-10%] h-[500px] w-[500px] rounded-full bg-blue-600/10 blur-[120px] animate-pulse delay-1000" />
        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:40px_40px] [mask-image:radial-gradient(ellipse_80%_80%_at_50%_50%,#000_70%,transparent_100%)]" />
      </div>

      <div
        className={cn(
          "z-10 hidden flex-col border-r border-slate-800 bg-slate-900/60 backdrop-blur-xl md:flex transition-all duration-300 ease-in-out",
          isCollapsed ? "w-20" : "w-72",
        )}
      >
        <SidebarContent
          isCollapsed={isCollapsed}
          toggleSidebar={toggleSidebar}
          setIsMobileMenuOpen={setIsMobileMenuOpen}
          handleNewChat={handleNewChat}
          sessions={sessions}
          currentSessionId={currentSessionId}
          loadSession={loadSession}
          handleRenameSession={handleRenameSession}
          handlePinSession={handlePinSession}
          handleDeleteSession={handleDeleteSession}
          isSettingsOpen={isSettingsOpen}
          setIsSettingsOpen={setIsSettingsOpen}
          setIsProfileOpen={setIsProfileOpen}
          user={user}
          navigate={navigate}
          logout={logout}
        />
      </div>

      {isMobileMenuOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden">
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setIsMobileMenuOpen(false)}
          />
          <div className="relative flex w-72 max-w-[85vw] flex-col border-r border-slate-800 bg-slate-900 shadow-2xl animate-in slide-in-from-left duration-300">
            <SidebarContent
              isCollapsed={false}
              toggleSidebar={toggleSidebar}
              setIsMobileMenuOpen={setIsMobileMenuOpen}
              handleNewChat={handleNewChat}
              sessions={sessions}
              currentSessionId={currentSessionId}
              loadSession={loadSession}
              handleRenameSession={handleRenameSession}
              handlePinSession={handlePinSession}
              handleDeleteSession={handleDeleteSession}
              isSettingsOpen={isSettingsOpen}
              setIsSettingsOpen={setIsSettingsOpen}
              setIsProfileOpen={setIsProfileOpen}
              user={user}
              navigate={navigate}
              logout={logout}
            />
          </div>
        </div>
      )}

      <UserProfileDialog
        isOpen={isProfileOpen}
        onClose={() => setIsProfileOpen(false)}
      />

      <ConfirmModal
        isOpen={isDeleteModalOpen}
        title="Xóa cuộc trò chuyện?"
        message="Bạn có chắc chắn muốn xóa cuộc trò chuyện này? Toàn bộ lịch sử tin nhắn sẽ bị mất vĩnh viễn."
        onConfirm={confirmDeleteSession}
        onCancel={() => setIsDeleteModalOpen(false)}
      />

      <RenameModal
        isOpen={isRenameModalOpen}
        title="Đổi tên cuộc trò chuyện"
        initialValue={selectedSessionTitle}
        onRename={confirmRenameSession}
        onCancel={() => setIsRenameModalOpen(false)}
      />

      <div className="flex flex-1 flex-col z-10 relative">
        <header className="flex h-16 items-center border-b border-slate-800 bg-slate-900/40 backdrop-blur-md px-4 md:hidden justify-between">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              className="text-slate-400 hover:text-cyan-400 hover:bg-cyan-500/10"
              onClick={() => setIsMobileMenuOpen(true)}
            >
              <Menu className="h-5 w-5" />
            </Button>
            <span className="font-bold text-slate-100">AI Chat-Bot</span>
          </div>
        </header>

        <div ref={chatContainerRef} className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center p-8 opacity-50 space-y-4">
              <Bot className="h-16 w-16 text-cyan-500/50" />
              <div className="text-xl font-medium text-slate-300">
                Bắt đầu cuộc trò chuyện mới
              </div>
              <p className="text-slate-500 max-w-md">
                Hãy đặt câu hỏi hoặc yêu cầu hỗ trợ, tôi sẽ giúp bạn giải quyết
                vấn đề.
              </p>
            </div>
          )}

          {messages.map((msg, index) => (
            <div
              key={index}
              className={cn(
                "flex w-full gap-4 max-w-3xl mx-auto",
                msg.role === "user" ? "justify-end" : "justify-start",
              )}
            >
              {msg.role === "ai" && (
                <div className="flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-full bg-cyan-900/30 border border-cyan-500/30 text-cyan-400 shadow-[0_0_15px_-3px_rgba(6,182,212,0.4)]">
                  <Bot className="h-5 w-5" />
                </div>
              )}

              <div
                className={cn(
                  "relative px-5 py-3.5 text-sm md:text-base leading-relaxed shadow-lg max-w-[85%] md:max-w-[75%]",
                  msg.role === "user"
                    ? "bg-gradient-to-br from-blue-600 to-cyan-600 text-white rounded-2xl rounded-tr-sm border border-cyan-400/20"
                    : "bg-slate-800/60 backdrop-blur-sm text-slate-100 rounded-2xl rounded-tl-sm border border-slate-700/50",
                )}
              >
                <div
                  className={cn(
                    "prose prose-sm prose-invert max-w-none break-words text-slate-100",
                    "prose-p:mb-3 prose-p:last:mb-0 prose-p:leading-[1.7]",
                    "prose-ul:m-0 prose-ul:pl-5 prose-ul:mb-3 prose-ul:list-disc",
                    "prose-li:m-0 prose-li:mb-1",
                    "prose-strong:font-bold prose-strong:text-cyan-300",
                    "prose-code:bg-slate-900/50 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-cyan-200"
                  )}
                >
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm, remarkBreaks]}
                    components={{
                      p: ({ node, ...props }) => (
                        <p className="my-2 leading-[1.7] first:mt-0 last:mb-0" {...props} />
                      ),
                      ul: ({ node, ...props }) => (
                        <ul className="my-2 list-disc pl-5 space-y-1" {...props} />
                      ),
                      ol: ({ node, ...props }) => (
                        <ol className="my-2 list-decimal pl-5 space-y-1" {...props} />
                      ),
                      li: ({ node, ...props }) => (
                        <li className="my-0 leading-[1.7]" {...props} />
                      )
                    }}
                  >
                    {msg.role === "ai" ? formatAssistantContent(msg.content) : msg.content}
                  </ReactMarkdown>
                </div>

                {/* Source Documents Section */}
                {msg.role === "ai" && msg.sources && msg.sources.length > 0 && (
                  <div className="mt-4 pt-3 border-t border-slate-700/50">
                    <div className="flex items-center gap-2 text-xs text-slate-400 mb-2">
                      <FileText className="h-3.5 w-3.5" />
                      <span className="font-medium">Tài liệu tham khảo:</span>
                    </div>
                    <div className="flex flex-col gap-1.5">
                      {msg.sources.map((source, idx) => (
                        <a
                          key={idx}
                          href={API_ENDPOINTS.DOCUMENTS.CONTENT(source.doc_id)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-slate-800/50 hover:bg-slate-700/50 border border-slate-700/30 hover:border-cyan-500/30 transition-all group text-xs"
                        >
                          <FileText className="h-3.5 w-3.5 text-cyan-500/70 group-hover:text-cyan-400" />
                          <span className="text-slate-300 group-hover:text-cyan-300 truncate flex-1">
                            {source.filename}
                          </span>
                          <Download className="h-3 w-3 text-slate-500 group-hover:text-cyan-400" />
                        </a>
                      ))}
                    </div>
                  </div>
                )}

                {/* Document Suggestion - Only show on last AI message with related docs */}
                {msg.role === "ai" &&
                  msg.has_related_docs &&
                  (!msg.sources || msg.sources.length === 0) &&
                  index === messages.length - 1 && (
                    <div className="mt-3 pt-3 border-t border-slate-700/30">
                      <button
                        onClick={() => {
                          setInputValue("Cho tôi xem tài liệu tham khảo");
                          setTimeout(() => handleSendMessage(), 100);
                        }}
                        className="flex items-center gap-2 px-3 py-2 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 hover:border-cyan-400 transition-all text-xs text-cyan-400 hover:text-cyan-300"
                      >
                        <FileText className="h-3.5 w-3.5" />
                        <span>Bạn có muốn xem tài liệu tham khảo không?</span>
                      </button>
                    </div>
                  )}
              </div>

              {msg.role === "user" && (
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
              <div className="text-slate-400 text-sm flex items-center">
                Đang suy nghĩ...
              </div>
            </div>
          )}
        </div>

        <div className="p-4 md:p-6 pt-2">
          <div className="mx-auto max-w-3xl relative">
            <div className="relative flex items-end gap-2 rounded-xl border border-slate-700/50 bg-slate-900/60 p-2 shadow-2xl backdrop-blur-xl ring-offset-2 focus-within:ring-2 focus-within:ring-cyan-500/50 focus-within:border-cyan-500/50 transition-all duration-300">
              <Input
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) =>
                  e.key === "Enter" && !isTyping && handleSendMessage()
                }
                className="min-h-[44px] w-full resize-none border-0 bg-transparent px-3 py-2.5 text-slate-100 placeholder:text-slate-500 focus-visible:ring-0 focus-visible:ring-offset-0 disabled:opacity-50"
                placeholder={
                  isTyping
                    ? "AI đang trả lời..."
                    : "Nhập lệnh hoặc câu hỏi của bạn..."
                }
                disabled={isTyping}
              />
              <Button
                onClick={handleSendMessage}
                size="icon"
                disabled={isTyping || !inputValue.trim()}
                className="h-10 w-10 shrink-0 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-all shadow-[0_0_10px_-2px_rgba(6,182,212,0.5)] hover:shadow-[0_0_15px_-2px_rgba(6,182,212,0.7)] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isTyping ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <Send className="h-5 w-5" />
                )}
              </Button>
            </div>
            <div className="mt-2 text-center text-xs text-slate-600">
              AI-ChatBot | Hệ thống sẵn sàng
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatLayout;
