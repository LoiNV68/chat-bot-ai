import { createContext, useContext, useState, useEffect, ReactNode, useMemo } from 'react';
import axios from 'axios';
import { API_ENDPOINTS } from '@/config/api';

type UserRole = 'admin' | 'lecturer' | 'user';

interface User {
    id: number;
    email: string;
    full_name: string;
    is_active: boolean;
    is_superuser: boolean;
    role?: UserRole;
}

interface AuthContextType {
    user: User | null;
    token: string | null;
    login: (token: string, refreshToken: string) => Promise<void>;
    logout: () => void;
    isLoading: boolean;
    isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
    const [user, setUser] = useState<User | null>(null);
    const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
    const [refreshToken, setRefreshToken] = useState<string | null>(localStorage.getItem('refresh_token'));
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const initAuth = async () => {
            if (token) {
                try {
                    // Xác thực token và lấy thông tin người dùng
                    // Giả sử chúng ta có endpoint /api/v1/auth/me
                    const response = await axios.get(API_ENDPOINTS.AUTH.ME, {
                        headers: { Authorization: `Bearer ${token}` }
                    });
                    setUser(response.data);
                } catch (error) {
                    // Nếu 401/403, thử refresh token
                    try {
                        if (refreshToken) {
                           const refreshResponse = await axios.post(API_ENDPOINTS.AUTH.REFRESH, null, {
                               params: { refresh_token: refreshToken }
                           });
                           const newAccessToken = refreshResponse.data.access_token;
                           const newRefreshToken = refreshResponse.data.refresh_token;

                           login(newAccessToken, newRefreshToken);
                           // Lấy lại user được xử lý bởi state change, nhưng để an toàn/nhanh:
                           // setUser(await fetchUser(newAccessToken)); // Tùy chọn
                           return; 
                        }
                    } catch (refreshError) {
                         console.error("RefreshToken invalid or expired", refreshError);
                    }
                    console.error("Token invalid or expired", error);
                    logout();
                }
            }
            setIsLoading(false);
        };

        const interceptor = axios.interceptors.response.use(
            (response) => response,
            async (error) => {
                const originalRequest = error.config;
                if ((error.response?.status === 401 || error.response?.status === 403) && !originalRequest._retry) {
                    originalRequest._retry = true;
                    try {
                        const storedRefreshToken = localStorage.getItem('refresh_token');
                        if (storedRefreshToken) {
                            const response = await axios.post(API_ENDPOINTS.AUTH.REFRESH, null, {
                                params: { refresh_token: storedRefreshToken }
                            });
                            
                            const { access_token, refresh_token } = response.data;
                            
                            login(access_token, refresh_token);
                            
                            originalRequest.headers.Authorization = `Bearer ${access_token}`;
                            return axios(originalRequest);
                        }
                    } catch (refreshError) {
                        logout();
                        return Promise.reject(refreshError);
                    }
                }
                return Promise.reject(error);
            }
        );

        initAuth();

        return () => {
            axios.interceptors.response.eject(interceptor);
        };
    }, [token]);

    const login = async (newToken: string, newRefreshToken: string) => {
        setToken(newToken);
        setRefreshToken(newRefreshToken);
        localStorage.setItem('token', newToken);
        localStorage.setItem('refresh_token', newRefreshToken);
    };

    const logout = () => {
        setToken(null);
        setRefreshToken(null);
        setUser(null);
        localStorage.removeItem('token');
        localStorage.removeItem('refresh_token');
    };

    // Sử dụng useMemo để tránh tạo object mới mỗi render
    const contextValue = useMemo(() => ({
        user,
        token,
        login,
        logout,
        isLoading,
        isAuthenticated: !!user
    }), [user, token, isLoading]);

    return (
        <AuthContext.Provider value={contextValue}>

            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth phải được sử dụng trong AuthProvider');
    }
    return context;
};
