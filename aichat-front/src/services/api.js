import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // Allow self-signed certificates in development
  httpsAgent: process.env.NODE_ENV === 'development' ? {
    rejectUnauthorized: false
  } : undefined
});

// Request interceptor to add auth token
// Axios 요청 인터셉터? 모든 요청이 서버로 전송되기 전에 반드시 거침 (자동 토큰 주입 역할)
api.interceptors.request.use(
  (config) => {
    const token = sessionStorage.getItem('access_token');

    // DEBUG
    console.log('[API] Request:', config.method?.toUpperCase(), config.url);
    console.log('[API] Token:', token ? `${token.substring(0, 20)}...` : 'NULL');

    if (token) {
      config.headers.Authorization = `Bearer ${token}`; // 인터셉트가 알아서 토큰을 넣어줌
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Skip redirect for login endpoint (let Login component show error)
      const isLoginRequest = error.config?.url?.includes('/auth/login');
      if (!isLoginRequest) {
        // Unauthorized - clear session and redirect to login
        alert('세션이 만료되었습니다. 다시 로그인해 주세요.');
        sessionStorage.clear();
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  login: async (username, password) => {
    const response = await api.post('/api/auth/login', {
      username,
      password
    });
    return response.data;
  },

  logout: async (sessionId) => {
    const response = await api.post('/api/auth/logout', null, {
      params: { session_id: sessionId }
    });
    return response.data;
  }
};

// Chat API
export const chatAPI = {
  sendMessage: async (message, sessionId) => {
    const response = await api.post('/api/chat/', {
      message,
      session_id: sessionId
    });
    return response.data;
  },

  getHistory: async (sessionId) => {
    const response = await api.get(`/api/chat/history/${sessionId}`);
    return response.data;
  },

  submitFeedback: async (messageId, rating) => {
    const response = await api.patch(`/api/chat/messages/${messageId}/feedback`, { rating });
    return response.data;
  }
};

// Session API
export const sessionAPI = {
  clearServiceHistory: async (serviceType) => {
    const response = await api.post('/api/session/new', {
      service_type: serviceType
    });
    return response.data;
  }
};

// Glossary API
export const glossaryAPI = {
  query: async (query, sessionId) => {
    const response = await api.post('/api/glossary/query', {
      query,
      session_id: sessionId
    });
    return response.data;
  },

  getHistory: async (sessionId) => {
    const response = await api.get(`/api/glossary/history/${sessionId}`);
    return response.data;
  },

  submitFeedback: async (messageId, rating) => {
    const response = await api.patch(`/api/glossary/messages/${messageId}/feedback`, { rating });
    return response.data;
  }
};

// Work Guide API
export const workGuideAPI = {
  sendMessage: async (message, sessionId) => {
    const response = await api.post('/api/work-guide/', {
      message,
      session_id: sessionId
    });
    return response.data;
  },

  getHistory: async (sessionId) => {
    const response = await api.get(`/api/work-guide/history/${sessionId}`);
    return response.data;
  },

  submitFeedback: async (messageId, rating) => {
    const response = await api.patch(`/api/work-guide/messages/${messageId}/feedback`, { rating });
    return response.data;
  }
};

// History API
export const historyAPI = {
  getSessions: async (serviceType) => {
    const response = await api.get('/api/history/sessions', {
      params: { service_type: serviceType }
    });
    return response.data;
  },

  getSessionMessages: async (sessionId, serviceType) => {
    const response = await api.get(`/api/history/sessions/${sessionId}/messages`, {
      params: { service_type: serviceType }
    });
    return response.data;
  }
};

export default api;
