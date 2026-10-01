import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5000/api';

// Create axios instance
const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' }
});

// Auto-attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// A 401 on a signed-in request means the session is no longer valid (expired, or signed with an old key):
// sign out and go to the sign-in page. A 401 from the sign-in form itself is just a wrong e-mail or password -
// the form shows it; reloading the page would wipe that message.
export function isSignInRequest(url = '') {
  return /\/auth\/(login|register|google-login)$/.test(url);
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !isSignInRequest(error.config?.url)) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      if (window.location.pathname !== '/auth') window.location.href = '/auth';
    }
    return Promise.reject(error);
  }
);

// ── AUTH ──────────────────────────────────────────────────────────────────────
export const authAPI = {
  register: (data) => api.post('/auth/register', data),
  login:    (data) => api.post('/auth/login',    data),
  googleLogin: (data) => api.post('/auth/google-login', data),
  profile:  ()     => api.get('/auth/profile'),
  changePassword: (data) => api.post('/auth/change-password', data),
};

// ── MEASUREMENTS ──────────────────────────────────────────────────────────────
export const measurementsAPI = {
  save:      (data) => api.post('/measurements/',     data),
  getAll:    ()     => api.get('/measurements/'),
  getOne:    (id)   => api.get(`/measurements/${id}`),
  update:    (id, data) => api.put(`/measurements/${id}`, data),
  delete:    (id)   => api.delete(`/measurements/${id}`),
};

// ── IMAGES ────────────────────────────────────────────────────────────────────
export const imagesAPI = {
  upload:  (formData) => api.post('/images/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  analyse: (id)       => api.post(`/images/${id}/analyse`),
  confirmAttributes: (id, data) => api.post(`/images/${id}/confirm-attributes`, data),
  getAll:  ()         => api.get('/images/'),
  getOne:  (id)       => api.get(`/images/${id}`),
  delete:  (id)       => api.delete(`/images/${id}`),
  modelStatus: ()     => api.get('/images/model-status'),
};

// ── PATTERNS ──────────────────────────────────────────────────────────────────
export const patternsAPI = {
  generate: (data) => api.post('/patterns/generate', data),
  getAll:   ()     => api.get('/patterns/'),
  getOne:   (id)   => api.get(`/patterns/${id}`),
  // deletes the saved pattern and its PDFs; the customer and measurements are kept
  delete:   (id)   => api.delete(`/patterns/${id}`),
};

// ── EXPORT ────────────────────────────────────────────────────────────────────
export const exportAPI = {
  yardage:  (id, data) => api.post(`/export/yardage/${id}`, data),
  // fabric requirement for 36", 45" and 60" in one call; data: { selected_width_cm?, cutting_mode? }
  estimates: (id, data) => api.post(`/export/estimates/${id}`, data),
  pdf:      (id)       => api.post(`/export/pdf/${id}`),
  download: (id)       => api.get(`/export/download/${id}`, {
    responseType: 'blob'
  }),
  delete:   (id)       => api.delete(`/export/${id}`),
  getAll:   ()         => api.get('/export/'),
};

// ── RESEARCH METRICS ──────────────────────────────────────────────────────────
// Only the optional ease-of-use rating is part of the customer workflow; study-wide research
// endpoints are internal (researcher accounts, not linked from the app).
export const researchAPI = {
  submitFeedback: (data) => api.post('/research/feedback', data),
};

// ── FABRIC RECOMMENDATION ─────────────────────────────────────────────────────
export const fabricAPI = {
  getRecommendations: (data) => api.post('/fabric/recommend', data),
  getCatalog:         ()     => api.get('/fabric/catalog'),
  getOne:             (id)   => api.get(`/fabric/${id}`)
};

export default api;
