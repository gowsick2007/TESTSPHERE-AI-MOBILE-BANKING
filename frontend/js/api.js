/**
 * TestSphere AI — Central API client & state mediator
 */

const API_BASE = '/api';

// Simple state storage
const state = {
  token: localStorage.getItem('ts_token') || '',
  username: localStorage.getItem('ts_user') || 'Guest User',
  role: localStorage.getItem('ts_role') || 'VIEWER',
  authenticated: localStorage.getItem('ts_auth') === 'true'
};

/**
 * Perform a generic HTTP fetch with token and handling.
 */
async function apiFetch(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  
  // Set headers
  const headers = options.headers || {};
  headers['Content-Type'] = 'application/json';
  if (state.token) {
    headers['Authorization'] = `Bearer ${state.token}`;
  }

  // Handle URL params for token if endpoint requires it
  let finalUrl = url;
  if (state.token && (options.method === 'POST' || options.method === 'DELETE')) {
    const separator = url.includes('?') ? '&' : '?';
    finalUrl = `${url}${separator}token=${state.token}`;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 10000); // 10s timeout

  const fetchOptions = {
    ...options,
    headers,
    signal: controller.signal
  };

  try {
    const response = await fetch(finalUrl, fetchOptions);
    clearTimeout(timeoutId);
    
    // Check for HTTP errors
    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      const msg = errData.detail || `The request could not be completed (HTTP ${response.status})`;
      throw new Error(msg);
    }
    
    return await response.json();
  } catch (error) {
    clearTimeout(timeoutId);
    // Note: main catch block
    let errorMsg = error.message;
    if (error.name === 'AbortError') {
      errorMsg = 'Request timed out. The server is taking too long to respond.';
    } else if (errorMsg.includes('Failed to fetch')) {
      errorMsg = 'Unable to connect to the TestSphere service. Please check if backend is running.';
    }
    console.error(`API Fetch Failure [${endpoint}]:`, error);
    showToast(errorMsg, 'danger');
    throw new Error(errorMsg);
  }
}

/**
 * Long-timeout fetch (30s) for heavy operations: dependency graph, experiment benchmarks.
 * Each call gets its own AbortController — do NOT share one across multiple requests.
 */
async function apiFetchLong(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const headers = options.headers || {};
  headers['Content-Type'] = 'application/json';
  if (state.token) {
    headers['Authorization'] = `Bearer ${state.token}`;
  }

  let finalUrl = url;
  if (state.token && (options.method === 'POST' || options.method === 'DELETE')) {
    const separator = url.includes('?') ? '&' : '?';
    finalUrl = `${url}${separator}token=${state.token}`;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout

  try {
    const response = await fetch(finalUrl, { ...options, headers, signal: controller.signal });
    clearTimeout(timeoutId);
    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      const msg = errData.detail || `HTTP ${response.status}`;
      throw new Error(msg);
    }
    return await response.json();
  } catch (error) {
    clearTimeout(timeoutId);
    let errorMsg = error.message;
    if (error.name === 'AbortError') {
      errorMsg = 'Request timed out after 30 seconds. The server took too long to respond.';
    } else if (errorMsg.includes('Failed to fetch')) {
      errorMsg = 'Unable to connect to the TestSphere service. Please check if the backend is running.';
    }
    console.error(`API Long-Fetch Failure [${endpoint}]:`, error);
    throw new Error(errorMsg);
  }
}

/**
 * Shows an elegant toast notification.
 */
function showToast(message, type = 'primary') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  
  let iconClass = 'fa-info-circle';
  if (type === 'success') iconClass = 'fa-check-circle';
  if (type === 'danger') iconClass = 'fa-exclamation-triangle';
  if (type === 'warning') iconClass = 'fa-exclamation-circle';

  toast.innerHTML = `
    <i class="fas ${iconClass}"></i>
    <div>${message}</div>
  `;

  container.appendChild(toast);

  // Auto-remove after 4.5 seconds
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.3s';
    setTimeout(() => toast.remove(), 300);
  }, 4500);
}

// Exportable API Functions
const API = {
  state,
  showToast,
  fetchLong: apiFetchLong,

  async login(username, password) {
    try {
      const res = await apiFetch('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password })
      });

      if (res.success) {
        state.token = res.token;
        state.username = res.username;
        state.role = res.role;
        state.authenticated = true;

        localStorage.setItem('ts_token', res.token);
        localStorage.setItem('ts_user', res.username);
        localStorage.setItem('ts_role', res.role);
        localStorage.setItem('ts_auth', 'true');
        
        showToast(`Welcome back, ${res.username}! logged in as ${res.role}`, 'success');
        return true;
      } else {
        showToast(res.error || 'Login verification failed.', 'danger');
        return false;
      }
    } catch (e) {
      return false;
    }
  },

  async logout() {
    try {
      await apiFetch('/auth/logout', { method: 'POST' });
    } catch (e) {}

    state.token = '';
    state.username = 'Guest User';
    state.role = 'VIEWER';
    state.authenticated = false;

    localStorage.removeItem('ts_token');
    localStorage.removeItem('ts_user');
    localStorage.removeItem('ts_role');
    localStorage.removeItem('ts_auth');

    showToast('Logged out successfully.', 'primary');
    setTimeout(() => {
      window.location.href = '/';
    }, 500);
  },

  async checkSession() {
    try {
      const res = await apiFetch('/auth/me');
      state.username = res.username;
      state.role = res.role;
      state.authenticated = res.authenticated;
      
      localStorage.setItem('ts_user', res.username);
      localStorage.setItem('ts_role', res.role);
      localStorage.setItem('ts_auth', res.authenticated ? 'true' : 'false');
      
      if (!res.authenticated) {
        state.token = '';
        localStorage.removeItem('ts_token');
        localStorage.removeItem('ts_user');
        localStorage.removeItem('ts_role');
        localStorage.removeItem('ts_auth');
      }
      
      return res;
    } catch (e) {
      state.authenticated = false;
      state.token = '';
      localStorage.setItem('ts_auth', 'false');
      localStorage.removeItem('ts_token');
      localStorage.removeItem('ts_user');
      localStorage.removeItem('ts_role');
      return null;
    }
  },

  async fetchHealthStatus() {
    return await apiFetch('/data/status');
  },

  async loadDemoDataset() {
    return await apiFetch('/data/demo', { method: 'POST' });
  },

  async clearDataset(table) {
    return await apiFetch(`/data/${table}`, { method: 'DELETE' });
  },

  async analyzeChanges(payload) {
    return await apiFetch('/change/analyze', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  async registerChange(payload) {
    return await apiFetch('/change/register', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  async fetchSelection(payload) {
    return await apiFetchLong('/tests/selection', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  async runSmartRegression(payload) {
    return await apiFetch('/tests/run-smart', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  async runBaselineRegression() {
    return await apiFetch('/tests/run-baseline', { method: 'POST' });
  },

  async fetchTests() {
    return await apiFetch('/tests');
  },

  async fetchCoverageStats() {
    return await apiFetch('/tests/coverage');
  },

  async fetchFailureStats() {
    return await apiFetch('/tests/failures');
  },

  async fetchStrategy() {
    return await apiFetch('/strategy');
  },

  async switchStrategy(toStrategy, reason) {
    return await apiFetch('/strategy/rollback', {
      method: 'POST',
      body: JSON.stringify({ to_strategy: toStrategy, reason })
    });
  },

  async fetchStrategyHistory() {
    return await apiFetch('/strategy/history');
  },

  async fetchAuditLogs() {
    return await apiFetch('/audit/logs');
  },

  async submitFeedback(payload) {
    return await apiFetch('/audit/feedback', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  async fetchFeedbackStats() {
    return await apiFetch('/audit/feedback/stats');
  },

  async runWhatIfSimulation(payload) {
    return await apiFetchLong('/what-if', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  async runFailureScenarios() {
    return await apiFetch('/experiment/run-scenarios', { method: 'POST' });
  },

  async runExperimentBenchmark(payload) {
    return await apiFetch('/experiment/run', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  }
};

// Export to window object for other scripts to use
window.API = API;
