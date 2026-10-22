'use client'

import { useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { Send, Bot, User, Minimize2, Maximize2, X, Lightbulb, Zap, AlertCircle, CheckCircle } from 'lucide-react'
import { useAI } from '@/contexts/AIContext'

export default function AIAssistant() {
  const { currentPage, pageContext, userActions, isProcessing, logAction, assistWithAction, getProactiveSuggestions } = useAI()
  const [isOpen, setIsOpen] = useState(false)
  const [isMinimized, setIsMinimized] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const [showSuggestions, setShowSuggestions] = useState(true)
  const scrollRef = useRef(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  useEffect(() => {
    // Initial greeting with context
    const greeting = generateContextualGreeting()
    setMessages([{ role: 'assistant', content: greeting }])
  }, [currentPage])

  const generateContextualGreeting = () => {
    const pageName = pageContext.pageName || 'this page'
    return `Hello! I'm your EUCLID AI assistant. I can see you're on the ${pageName} page. I'm here to assist you with any action, change, or question you might have. I have full awareness of the platform and can help you navigate, optimize settings, troubleshoot issues, or explain any feature. What would you like to accomplish?`
  }

  const handleSend = async () => {
    if (!input.trim()) return

    const userMessage = { role: 'user', content: input }
    setMessages(prev => [...prev, userMessage])
    logAction('user_query', { query: input, page: currentPage })
    setInput('')
    setIsTyping(true)
    setShowSuggestions(false)

    // Generate intelligent response
    setTimeout(async () => {
      const response = await generateIntelligentResponse(input)
      setMessages(prev => [...prev, { role: 'assistant', content: response }])
      setIsTyping(false)
    }, 800)
  }

  const generateIntelligentResponse = async (query) => {
    const lowerQuery = query.toLowerCase()
    const context = pageContext
    
    // Page-specific intelligent responses
    if (currentPage === '/') {
      if (lowerQuery.includes('metric') || lowerQuery.includes('dashboard')) {
        return `Based on your dashboard, I can see you have access to real-time mining metrics, quantum compute utilization, and PHI scaling indicators. I can:\n• Explain any metric in detail\n• Set up custom alerts for threshold breaches\n• Generate performance reports\n• Compare current metrics against historical data\n\nWhich would you like me to help with?`
      }
    }

    if (currentPage.includes('mining')) {
      if (lowerQuery.includes('optimize') || lowerQuery.includes('efficiency')) {
        logAction('optimization_request', { type: 'mining' })
        const assistance = await assistWithAction('data_change', { type: 'mining_optimization' })
        return `I can help optimize your mining configuration. Based on current system analysis, I suggest:\n\n1. **Hashrate Optimization**: Adjust power limits to balance efficiency\n2. **Pool Selection**: Consider switching to pools with lower latency\n3. **Temperature Management**: Optimize cooling for better stability\n\n${assistance.guidance}\n\nWould you like me to implement any of these optimizations?`
      }
    }

    if (currentPage.includes('quantum')) {
      if (lowerQuery.includes('phi') || lowerQuery.includes('scaling')) {
        return `Phi scaling is a quantum-enhanced computational approach that leverages resonance geometry for exponential efficiency gains. On this page, you can:\n\n• Adjust PHI parameters for different workloads\n• Monitor quantum coherence times\n• Analyze resonance patterns\n• Optimize quantum circuit depth\n\nI can help you find the optimal PHI scaling factor for your current workload. Shall I run an analysis?`
      }
    }

    // Action and change assistance
    if (lowerQuery.includes('change') || lowerQuery.includes('modify') || lowerQuery.includes('update')) {
      const assistance = await assistWithAction('data_change', { query })
      let response = `I understand you want to make a change. Here's what I can help with:\n\n${assistance.guidance}\n\n`
      if (assistance.suggestions.length > 0) {
        response += '**Suggestions:**\n'
        assistance.suggestions.forEach((s, i) => response += `${i + 1}. ${s}\n`)
      }
      if (assistance.warnings.length > 0) {
        response += '\n**Warnings:**\n'
        assistance.warnings.forEach((w, i) => response += `⚠️ ${w}\n`)
      }
      return response
    }

    if (lowerQuery.includes('help') || lowerQuery.includes('assist') || lowerQuery.includes('what can you do')) {
      return `I'm your intelligent EUCLID assistant with full platform awareness. I can help you with:\n\n**Navigation & Discovery:**\n• Guide you to any feature or page\n• Explain platform capabilities\n• Suggest optimal workflows\n\n**Actions & Changes:**\n• Assist with any configuration change\n• Provide impact analysis before changes\n• Help troubleshoot issues\n• Optimize settings for your needs\n\n**Analysis & Insights:**\n• Explain metrics and data\n• Generate reports\n• Identify trends and anomalies\n• Provide recommendations\n\n**Page-Specific Help:**\n• Context-aware assistance for current page\n• Explain visible elements and their purpose\n• Suggest next steps based on context\n\nJust tell me what you want to accomplish, and I'll guide you through it!`
    }

    if (lowerQuery.includes('error') || lowerQuery.includes('problem') || lowerQuery.includes('issue')) {
      const assistance = await assistWithAction('error', { query })
      return `I'm here to help troubleshoot. ${assistance.guidance}\n\nI can:\n• Analyze error messages you're seeing\n• Check system status and logs\n• Suggest solutions based on the issue\n• Guide you through resolution steps\n\nPlease describe the error or issue you're experiencing, and I'll provide targeted assistance.`
    }

    if (lowerQuery.includes('how') || lowerQuery.includes('explain') || lowerQuery.includes('what is')) {
      return `I'd be happy to explain! Based on your current context (${context.pageName}), I can provide detailed explanations about:\n\n• Any visible element or metric\n• Platform features and capabilities\n• Technical concepts (quantum computing, PHI scaling, etc.)\n• Workflows and processes\n• Configuration options\n\nCould you specify what you'd like me to explain? I'll provide a clear, contextual explanation tailored to your current situation.`
    }

    // Database-related assistance
    if (lowerQuery.includes('database') || lowerQuery.includes('db') || lowerQuery.includes('migration')) {
      return `I can assist you with database operations and management:\n\n**Database Operations:**\n• Run database migrations\n• Check database connection status\n• View database schema and models\n• Perform data backups and restores\n• Monitor database performance\n\n**User Management:**\n• Create and manage user accounts\n• Update user permissions and roles\n• View user activity logs\n• Reset user passwords\n\n**Data Management:**\n• Query and analyze data\n• Export data reports\n• Perform data integrity checks\n• Optimize database performance\n\n**Migrations:**\n• Run pending migrations\n• Rollback to previous versions\n• View migration history\n• Create new migrations\n\nWhich database operation would you like me to help you with?`
    }

    if (lowerQuery.includes('user') || lowerQuery.includes('account') || lowerQuery.includes('permission')) {
      return `I can help you with user and account management:\n\n**User Operations:**\n• Create new user accounts (hybamine.com only)\n• Update user information\n• Manage user roles (Admin, User, Viewer)\n• Activate/deactivate user accounts\n• View user activity and login history\n\n**Permission Management:**\n• Assign role-based permissions\n• Configure access controls\n• Review security settings\n• Audit user permissions\n\n**Account Security:**\n• Reset user passwords\n• Enable two-factor authentication\n• Review login attempts\n• Manage session security\n\nWould you like me to help with a specific user or account operation?`
    }

    // Default intelligent response
    return `I understand you're asking about "${query}". Based on your current context on the ${context.pageName} page, I can help you:\n\n• Navigate to relevant features\n• Take specific actions\n• Make informed changes\n• Understand related concepts\n• Troubleshoot any issues\n• Manage database operations\n• Handle user authentication\n\nCould you provide more details about what you'd like to accomplish? I'm here to assist with anything you need.`
  }

  const handleSuggestionClick = (suggestion) => {
    setInput(suggestion)
    handleSend()
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const proactiveSuggestions = getProactiveSuggestions()

  if (!isOpen) {
    return (
      <div className="fixed bottom-6 right-6 z-50">
        <Button
          onClick={() => setIsOpen(true)}
          className="w-14 h-14 rounded-full bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 shadow-lg shadow-purple-500/20"
          size="icon"
        >
          <Bot className="w-6 h-6" />
        </Button>
        {showSuggestions && proactiveSuggestions.length > 0 && (
          <div className="absolute bottom-16 right-0 w-64 bg-slate-900/95 backdrop-blur-xl border border-purple-500/20 rounded-lg p-3 shadow-xl">
            <div className="flex items-center mb-2 text-purple-400">
              <Lightbulb className="w-4 h-4 mr-2" />
              <span className="text-sm font-medium">Suggestions</span>
            </div>
            {proactiveSuggestions.slice(0, 2).map((suggestion, index) => (
              <button
                key={index}
                onClick={() => {
                  setIsOpen(true)
                  handleSuggestionClick(suggestion.replace('Would you like me to ', '').replace('?', ''))
                }}
                className="w-full text-left text-xs text-slate-300 hover:text-white hover:bg-slate-800 rounded p-2 mb-1 transition-colors"
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <Card className={`fixed bottom-6 right-6 w-[400px] bg-slate-900/95 backdrop-blur-xl border-purple-500/20 shadow-2xl shadow-purple-500/10 z-50 transition-all duration-300 ${isMinimized ? 'h-16' : 'h-[650px]'}`}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3 bg-gradient-to-r from-purple-600/20 to-blue-600/20 rounded-t-lg">
        <div className="flex items-center space-x-2">
          <div className="relative">
            <Bot className="w-5 h-5 text-purple-400" />
            <div className="absolute -top-1 -right-1 w-2 h-2 bg-green-500 rounded-full animate-pulse" />
          </div>
          <CardTitle className="text-lg font-semibold text-white">EUCLID AI</CardTitle>
          {currentPage && (
            <Badge variant="outline" className="text-xs border-purple-500/30 text-purple-300">
              {pageContext.pageName}
            </Badge>
          )}
        </div>
        <div className="flex items-center space-x-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-slate-400 hover:text-white"
            onClick={() => setIsMinimized(!isMinimized)}
          >
            {isMinimized ? <Maximize2 className="w-4 h-4" /> : <Minimize2 className="w-4 h-4" />}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-slate-400 hover:text-white"
            onClick={() => setIsOpen(false)}
          >
            <X className="w-4 h-4" />
          </Button>
        </div>
      </CardHeader>
      {!isMinimized && (
        <CardContent className="flex flex-col h-[calc(100%-4rem)] p-0">
          <ScrollArea className="flex-1 p-4" ref={scrollRef}>
            <div className="space-y-4">
              {messages.map((message, index) => (
                <div
                  key={index}
                  className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`flex items-start space-x-2 max-w-[85%] ${
                      message.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''
                    }`}
                  >
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                        message.role === 'user'
                          ? 'bg-blue-600'
                          : 'bg-gradient-to-br from-purple-600 to-blue-600'
                      }`}
                    >
                      {message.role === 'user' ? (
                        <User className="w-4 h-4 text-white" />
                      ) : (
                        <Bot className="w-4 h-4 text-white" />
                      )}
                    </div>
                    <div
                      className={`p-3 rounded-lg ${
                        message.role === 'user'
                          ? 'bg-blue-600 text-white'
                          : 'bg-slate-800 text-slate-200 border border-slate-700'
                      }`}
                    >
                      <p className="text-sm whitespace-pre-wrap leading-relaxed">{message.content}</p>
                    </div>
                  </div>
                </div>
              ))}
              {isTyping && (
                <div className="flex justify-start">
                  <div className="flex items-start space-x-2 max-w-[85%]">
                    <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 bg-gradient-to-br from-purple-600 to-blue-600">
                      <Bot className="w-4 h-4 text-white" />
                    </div>
                    <div className="p-3 rounded-lg bg-slate-800 text-slate-200 border border-slate-700">
                      <div className="flex space-x-1">
                        <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" />
                        <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce delay-100" />
                        <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce delay-200" />
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </ScrollArea>
          {showSuggestions && proactiveSuggestions.length > 0 && messages.length === 1 && (
            <div className="px-4 py-2 border-t border-slate-700/50">
              <div className="flex items-center mb-2 text-purple-400">
                <Zap className="w-4 h-4 mr-2" />
                <span className="text-xs font-medium">Quick Actions</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {proactiveSuggestions.slice(0, 3).map((suggestion, index) => (
                  <Button
                    key={index}
                    variant="outline"
                    size="sm"
                    onClick={() => handleSuggestionClick(suggestion.replace('Would you like me to ', '').replace('?', ''))}
                    className="text-xs border-purple-500/30 text-purple-300 hover:bg-purple-500/10"
                  >
                    {suggestion.replace('Would you like me to ', '').replace('?', '')}
                  </Button>
                ))}
              </div>
            </div>
          )}
          <div className="p-4 border-t border-slate-700">
            <div className="flex space-x-2">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Ask me anything about the platform..."
                className="flex-1 bg-slate-800 border-slate-700 text-white placeholder:text-slate-500 focus:border-purple-500"
                disabled={isTyping}
              />
              <Button
                onClick={handleSend}
                disabled={!input.trim() || isTyping}
                className="bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700"
                size="icon"
              >
                {isTyping ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </Button>
            </div>
            <div className="flex items-center mt-2 text-xs text-slate-500">
              <CheckCircle className="w-3 h-3 mr-1 text-green-500" />
              <span>Full platform awareness • Context-sensitive • Always available</span>
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  )
}
