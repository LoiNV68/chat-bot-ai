// API Configuration
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const API_PREFIX = import.meta.env.VITE_API_PREFIX || "/api/v1";

export const API_URL = `${API_BASE_URL}${API_PREFIX}`;

// API Endpoints
export const API_ENDPOINTS = {
  // Auth
  AUTH: {
    LOGIN: `${API_URL}/auth/login`,
    REFRESH: `${API_URL}/auth/refresh`,
    ME: `${API_URL}/auth/me`,
  },
  // Chat
  CHAT: {
    SESSIONS: `${API_URL}/chat/sessions`,
    SESSION: (id: number | string) => `${API_URL}/chat/sessions/${id}`,
    MESSAGES: (sessionId: number | string) =>
      `${API_URL}/chat/sessions/${sessionId}/messages`,
    COMPLETION: `${API_URL}/chat/completion`,
  },
  // Users
  USERS: {
    BASE: `${API_URL}/users/`,
    DELETE: (id: number | string) => `${API_URL}/users/${id}`,
    TOGGLE_ADMIN: (id: number | string) =>
      `${API_URL}/users/${id}/toggle-admin`,
    TOGGLE_ACTIVE: (id: number | string) =>
      `${API_URL}/users/${id}/toggle-active`,
  },
  // Documents
  DOCUMENTS: {
    BASE: `${API_URL}/documents/`,
    TRASH: `${API_URL}/documents/trash`,
    UPLOAD: `${API_URL}/documents/upload`,
    BY_ID: (id: number | string) => `${API_URL}/documents/${id}`,
    CONTENT: (id: number | string) => `${API_URL}/documents/${id}/content`,
    RESTORE: (id: number | string) => `${API_URL}/documents/${id}/restore`,
  },
};

export default API_ENDPOINTS;
