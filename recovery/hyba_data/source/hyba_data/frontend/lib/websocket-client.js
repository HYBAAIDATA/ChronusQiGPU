/**
 * Enterprise WebSocket Client for Phi-Grover Frontend
 * 
 * Provides world-class WebSocket communication with:
 * - Automatic reconnection with exponential backoff
 * - Heartbeat/ping-pong for connection health
 * - Message acknowledgment and ordering
 * - Correlation ID tracking
 * - Structured error handling
 * - Event-driven architecture
 */

class WebSocketClient {
  constructor(url, options = {}) {
    this.url = url;
    this.options = {
      reconnectInterval: 1000,
      maxReconnectInterval: 30000,
      reconnectDecay: 1.5,
      maxReconnectAttempts: 10,
      heartbeatInterval: 30000,
      timeout: 10000,
      ...options
    };
    
    this.ws = null;
    this.connected = false;
    this.reconnectAttempts = 0;
    this.reconnectTimeout = null;
    this.heartbeatInterval = null;
    this.messageQueue = [];
    this.messageId = 0;
    this.pendingAcks = new Map();
    this.eventHandlers = new Map();
    this.correlationId = this.generateUUID();
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
   * Generate message ID
   */
  generateMessageId() {
    return `msg_${++this.messageId}_${Date.now()}`;
  }

  /**
   * Connect to WebSocket server
   */
  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN)) {
      return;
    }

    try {
      this.ws = new WebSocket(this.url);
      this.setupEventHandlers();
    } catch (error) {
      console.error('WebSocket connection error:', error);
      this.scheduleReconnect();
    }
  }

  /**
   * Setup WebSocket event handlers
   */
  setupEventHandlers() {
    this.ws.onopen = () => this.handleOpen();
    this.ws.onmessage = (event) => this.handleMessage(event);
    this.ws.onerror = (error) => this.handleError(error);
    this.ws.onclose = (event) => this.handleClose(event);
  }

  /**
   * Handle connection open
   */
  handleOpen() {
    console.log('WebSocket connected');
    this.connected = true;
    this.reconnectAttempts = 0;
    
    // Start heartbeat
    this.startHeartbeat();
    
    // Send queued messages
    this.flushMessageQueue();
    
    // Emit connected event
    this.emit('connected');
  }

  /**
   * Handle incoming message
   */
  handleMessage(event) {
    try {
      const message = JSON.parse(event.data);
      
      // Update correlation ID from server
      if (message.correlation_id) {
        this.correlationId = message.correlation_id;
      }
      
      // Handle acknowledgment
      if (message.type === 'ack') {
        this.handleAck(message);
        return;
      }
      
      // Handle heartbeat
      if (message.type === 'heartbeat') {
        this.emit('heartbeat', message.data);
        return;
      }
      
      // Handle error
      if (message.type === 'error') {
        this.emit('error', message.error);
        return;
      }
      
      // Handle response
      if (message.type === 'response') {
        this.emit(`response:${message.command}`, message.data);
        return;
      }
      
      // Handle other message types
      this.emit(message.type, message.data);
      
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
    }
  }

  /**
   * Handle acknowledgment
   */
  handleAck(message) {
    const messageId = message.data?.original_message_id;
    if (messageId && this.pendingAcks.has(messageId)) {
      const { resolve } = this.pendingAcks.get(messageId);
      resolve(message);
      this.pendingAcks.delete(messageId);
    }
  }

  /**
   * Handle WebSocket error
   */
  handleError(error) {
    console.error('WebSocket error:', error);
    this.emit('error', { type: 'websocket_error', message: error.message });
  }

  /**
   * Handle connection close
   */
  handleClose(event) {
    console.log('WebSocket closed:', event.code, event.reason);
    this.connected = false;
    this.stopHeartbeat();
    
    // Reject pending acknowledgments
    this.pendingAcks.forEach(({ reject }) => {
      reject(new Error('Connection closed'));
    });
    this.pendingAcks.clear();
    
    // Emit disconnected event
    this.emit('disconnected', { code: event.code, reason: event.reason });
    
    // Schedule reconnection
    if (event.code !== 1000) { // Normal close
      this.scheduleReconnect();
    }
  }

  /**
   * Schedule reconnection with exponential backoff
   */
  scheduleReconnect() {
    if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      this.emit('reconnect_failed');
      return;
    }
    
    const delay = Math.min(
      this.options.reconnectInterval * Math.pow(this.options.reconnectDecay, this.reconnectAttempts),
      this.options.maxReconnectInterval
    );
    
    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1})`);
    this.emit('reconnecting', { attempt: this.reconnectAttempts + 1, delay });
    
    this.reconnectTimeout = setTimeout(() => {
      this.reconnectAttempts++;
      this.connect();
    }, delay);
  }

  /**
   * Start heartbeat
   */
  startHeartbeat() {
    this.heartbeatInterval = setInterval(() => {
      this.send({
        type: 'heartbeat',
        data: { client_time: Date.now() }
      });
    }, this.options.heartbeatInterval);
  }

  /**
   * Stop heartbeat
   */
  stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  /**
   * Send message with acknowledgment
   */
  async send(message, waitForAck = false) {
    const messageId = this.generateMessageId();
    const fullMessage = {
      correlation_id: this.correlationId,
      message_id: messageId,
      ...message
    };
    
    if (!this.connected) {
      if (waitForAck) {
        return Promise.reject(new Error('WebSocket not connected'));
      }
      this.messageQueue.push(fullMessage);
      return;
    }
    
    try {
      this.ws.send(JSON.stringify(fullMessage));
      
      if (waitForAck) {
        return new Promise((resolve, reject) => {
          const timeout = setTimeout(() => {
            this.pendingAcks.delete(messageId);
            reject(new Error('Acknowledgment timeout'));
          }, this.options.timeout);
          
          this.pendingAcks.set(messageId, {
            resolve: (data) => {
              clearTimeout(timeout);
              resolve(data);
            },
            reject: (error) => {
              clearTimeout(timeout);
              reject(error);
            }
          });
        });
      }
    } catch (error) {
      console.error('Error sending WebSocket message:', error);
      throw error;
    }
  }

  /**
   * Flush message queue
   */
  flushMessageQueue() {
    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift();
      this.ws.send(JSON.stringify(message));
    }
  }

  /**
   * Register event handler
   */
  on(event, handler) {
    if (!this.eventHandlers.has(event)) {
      this.eventHandlers.set(event, []);
    }
    this.eventHandlers.get(event).push(handler);
  }

  /**
   * Remove event handler
   */
  off(event, handler) {
    if (this.eventHandlers.has(event)) {
      const handlers = this.eventHandlers.get(event);
      const index = handlers.indexOf(handler);
      if (index > -1) {
        handlers.splice(index, 1);
      }
    }
  }

  /**
   * Emit event
   */
  emit(event, data) {
    if (this.eventHandlers.has(event)) {
      this.eventHandlers.get(event).forEach(handler => {
        try {
          handler(data);
        } catch (error) {
          console.error(`Error in event handler for ${event}:`, error);
        }
      });
    }
  }

  /**
   * Send command
   */
  async sendCommand(command, data = {}) {
    return this.send({
      type: 'command',
      command,
      data
    }, true);
  }

  // Phi-Scaler specific commands

  /**
   * Set target hash rate
   */
  async setTarget(ehs) {
    return this.sendCommand('set_target', { ehs });
  }

  /**
   * Set pool mode
   */
  async setPool(mode) {
    return this.sendCommand('set_pool', { mode });
  }

  /**
   * Get status
   */
  async getStatus() {
    return this.sendCommand('status');
  }

  /**
   * Stop hardware
   */
  async stop() {
    return this.sendCommand('stop');
  }

  /**
   * Disconnect from server
   */
  disconnect() {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    
    this.stopHeartbeat();
    
    if (this.ws) {
      this.ws.close(1000, 'Client disconnecting');
      this.ws = null;
    }
    
    this.connected = false;
    this.emit('disconnected');
  }

  /**
   * Get connection status
   */
  isConnected() {
    return this.connected && this.ws && this.ws.readyState === WebSocket.OPEN;
  }
}

// Create global WebSocket client instance
const wsClient = new WebSocketClient(
  process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8765'
);

export default wsClient;
