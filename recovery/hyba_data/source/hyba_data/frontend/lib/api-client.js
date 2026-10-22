/**
 * Enterprise API Client for Phi-Grover Frontend
 * 
 * Provides world-class API communication with:
 * - Automatic correlation ID tracking
 * - Structured error handling
 * - Request/response interceptors
 * - Retry logic with exponential backoff
 * - Metrics collection
 */

class ApiClient {
  constructor(baseUrl = 'http://localhost:8000', options = {}) {
    this.baseUrl = baseUrl;
    this.options = {
      timeout: 30000,
      maxRetries: 3,
      retryDelay: 1000,
      ...options
    };
    this.metrics = {
      requests: 0,
      errors: 0,
      latency: []
    };
  }

  /**
   * Generate or retrieve correlation ID
   */
  getCorrelationId() {
    if (!this.correlationId) {
      this.correlationId = this.generateUUID();
    }
    return this.correlationId;
  }

  /**
   * Generate UUID v4
   */
  generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }

  /**
   * Build full URL from endpoint
   */
  buildUrl(endpoint) {
    return `${this.baseUrl}${endpoint}`;
  }

  /**
   * Get default headers.
   * The JWT lives in an httpOnly cookie — the browser sends it automatically
   * on same-origin requests.  No Authorization header injection needed here.
   */
  getHeaders(customHeaders = {}) {
    const headers = {
      'Content-Type': 'application/json',
      'X-Correlation-ID': this.getCorrelationId(),
      ...customHeaders
    };
    return headers;
  }

  /**
   * Record metrics
   */
  recordMetrics(latency, error = false) {
    this.metrics.requests++;
    if (error) this.metrics.errors++;
    this.metrics.latency.push(latency);
    
    // Keep only last 100 latency measurements
    if (this.metrics.latency.length > 100) {
      this.metrics.latency.shift();
    }
  }

  /**
   * Get metrics summary
   */
  getMetrics() {
    const avgLatency = this.metrics.latency.length > 0
      ? this.metrics.latency.reduce((a, b) => a + b, 0) / this.metrics.latency.length
      : 0;
    
    return {
      totalRequests: this.metrics.requests,
      totalErrors: this.metrics.errors,
      errorRate: this.metrics.requests > 0 ? this.metrics.errors / this.metrics.requests : 0,
      averageLatency: avgLatency
    };
  }

  /**
   * Sleep for retry delay
   */
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Handle API error response
   */
  handleError(response, data) {
    const correlationId = response.headers.get('X-Correlation-ID');
    
    // Structured error from backend
    if (data.error) {
      const error = new Error(data.error.message);
      error.code = data.error.code;
      error.correlationId = correlationId;
      error.details = data.error;
      throw error;
    }
    
    // Legacy error format
    if (data.detail) {
      const error = new Error(data.detail);
      error.correlationId = correlationId;
      throw error;
    }
    
    // Generic error
    const error = new Error(`HTTP ${response.status}: ${response.statusText}`);
    error.correlationId = correlationId;
    throw error;
  }

  /**
   * Make HTTP request with retry logic
   */
  async request(endpoint, options = {}, retryCount = 0) {
    const startTime = Date.now();
    const url = this.buildUrl(endpoint);
    
    try {
      const response = await fetch(url, {
        ...options,
        headers: this.getHeaders(options.headers)
      });

      const latency = Date.now() - startTime;
      
      // Handle non-OK responses
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        this.recordMetrics(latency, true);
        
        // Retry on 5xx errors
        if (response.status >= 500 && retryCount < this.options.maxRetries) {
          await this.sleep(this.options.retryDelay * Math.pow(2, retryCount));
          return this.request(endpoint, options, retryCount + 1);
        }
        
        this.handleError(response, data);
      }

      const data = await response.json().catch(() => ({}));
      this.recordMetrics(latency);
      
      return {
        data,
        correlationId: response.headers.get('X-Correlation-ID'),
        latency
      };

    } catch (error) {
      const latency = Date.now() - startTime;
      this.recordMetrics(latency, true);
      
      // Retry on network errors
      if (retryCount < this.options.maxRetries && error.name === 'TypeError') {
        await this.sleep(this.options.retryDelay * Math.pow(2, retryCount));
        return this.request(endpoint, options, retryCount + 1);
      }
      
      throw error;
    }
  }

  /**
   * GET request
   */
  async get(endpoint, options = {}) {
    return this.request(endpoint, {
      method: 'GET',
      ...options
    });
  }

  /**
   * POST request
   */
  async post(endpoint, data, options = {}) {
    return this.request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
      ...options
    });
  }

  /**
   * PUT request
   */
  async put(endpoint, data, options = {}) {
    return this.request(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
      ...options
    });
  }

  /**
   * DELETE request
   */
  async delete(endpoint, options = {}) {
    return this.request(endpoint, {
      method: 'DELETE',
      ...options
    });
  }

  // Phi-Scaler specific endpoints

  /**
   * Scale hardware (switch pool/target)
   */
  async scaleHardware(config) {
    return this.post('/api/v1/hardware/scale', config);
  }

  /**
   * Get hardware status
   */
  async getHardwareStatus() {
    return this.get('/api/v1/hardware/status');
  }

  /**
   * Start hardware
   */
  async startHardware() {
    return this.post('/api/v1/hardware/start', {});
  }

  /**
   * Stop hardware
   */
  async stopHardware() {
    return this.post('/api/v1/hardware/stop', {});
  }

  /**
   * Get pool strategies
   */
  async getPoolStrategies() {
    return this.get('/api/v1/pools/strategies');
  }

  /**
   * Connect to pool
   */
  async connectPool(poolName, username, worker, password = '') {
    return this.post('/api/v1/pool/connect', {
      pool_name: poolName,
      username,
      worker,
      password
    });
  }

  /**
   * Get pool status
   */
  async getPoolStatus() {
    return this.get('/api/v1/pool/status');
  }

  /**
   * Get resonance map
   */
  async getResonanceMap() {
    return this.get('/api/v1/resonance/map');
  }

  /**
   * Get thermal status
   */
  async getThermalStatus() {
    return this.get('/api/v1/hardware/thermal');
  }

  /**
   * Get market conditions
   */
  async getMarketConditions() {
    return this.get('/api/v1/market/conditions');
  }

  // Authentication endpoints

  /**
   * Login
   */
  async login(email, password) {
    return this.post('/api/auth/login', { email, password });
  }

  /**
   * Verify authentication
   */
  async verifyAuth() {
    return this.get('/api/auth/verify');
  }

  // User management endpoints

  /**
   * Get users (admin only)
   */
  async getUsers() {
    return this.get('/api/users');
  }

  /**
   * Create user (admin only)
   */
  async createUser(userData) {
    return this.post('/api/users', userData);
  }

  /**
   * Update user (admin only)
   */
  async updateUser(email, userData) {
    return this.put(`/api/users/${email}`, userData);
  }

  /**
   * Delete user (admin only)
   */
  async deleteUser(email) {
    return this.delete(`/api/users/${email}`);
  }
}

// Create global API client instance
const apiClient = new ApiClient(
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
);

export default apiClient;
