const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// ── Token management ──────────────────────────────────────────────────────────
export const auth = {
  getToken: () => localStorage.getItem('access_token'),
  setTokens: (access, refresh) => {
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);
  },
  clearTokens: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  },
  isAuthenticated: () => !!localStorage.getItem('access_token'),
};

// ── Base fetch wrapper ────────────────────────────────────────────────────────
async function request(path, options = {}) {
  const token = auth.getToken();
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    auth.clearTokens();
    window.location.reload();
    return;
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }

  if (res.status === 204) return null;
  return res.json();
}

// ── Auth API ──────────────────────────────────────────────────────────────────
export const authApi = {
  register: (email, password, fullName) =>
    request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, full_name: fullName }),
    }),

  login: async (email, password) => {
    const data = await request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    auth.setTokens(data.access_token, data.refresh_token);
    return data;
  },

  me: () => request('/auth/me'),

  logout: () => auth.clearTokens(),
};

// ── Documents API ─────────────────────────────────────────────────────────────
export const documentsApi = {
  list: (page = 1, pageSize = 50) =>
    request(`/documents/?page=${page}&page_size=${pageSize}`),

  ingest: (title, content, source) =>
    request('/documents/', {
      method: 'POST',
      body: JSON.stringify({ title, content, source }),
    }),

  upload: async (file, title) => {
    const token = auth.getToken();
    const form = new FormData();
    form.append('file', file);
    const url = `${API_BASE}/documents/upload${title ? `?title=${encodeURIComponent(title)}` : ''}`;
    const res = await fetch(url, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Upload failed');
    }
    return res.json();
  },

  delete: (id) => request(`/documents/${id}`, { method: 'DELETE' }),

  query: (query, topK = 5, similarityThreshold = 0.7) =>
    request('/documents/query', {
      method: 'POST',
      body: JSON.stringify({ query, top_k: topK, similarity_threshold: similarityThreshold }),
    }),

  // Returns a ReadableStream for SSE streaming
  queryStream: (query, topK = 5, similarityThreshold = 0.7) => {
    const token = auth.getToken();
    return fetch(`${API_BASE}/documents/query/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ query, top_k: topK, similarity_threshold: similarityThreshold }),
    });
  },
};
