'use client'

import { createContext, useContext, useState, useEffect, useRef } from 'react'

const AIContext = createContext()

export function AIProvider({ children }) {
  const [currentPage, setCurrentPage] = useState('/')
  const [pageContext, setPageContext] = useState({})
  const [userActions, setUserActions] = useState([])
  const [isProcessing, setIsProcessing] = useState(false)
  const actionHistoryRef = useRef([])

  // Track current page and context
  useEffect(() => {
    const handleRouteChange = () => {
      setCurrentPage(window.location.pathname)
      updatePageContext()
    }

    window.addEventListener('popstate', handleRouteChange)
    handleRouteChange()

    return () => window.removeEventListener('popstate', handleRouteChange)
  }, [])

  // Update page context based on current URL
  const updatePageContext = () => {
    const path = window.location.pathname
    const context = {
      path,
      pageName: getPageName(path),
      elements: getPageElements(),
      state: getPageState()
    }
    setPageContext(context)
  }

  const getPageName = (path) => {
    if (path === '/') return 'Dashboard'
    if (path === '/login') return 'Login'
    if (path.includes('mining')) return 'Mining Operations'
    if (path.includes('quantum')) return 'Quantum Computing'
    if (path.includes('analytics')) return 'Analytics'
    if (path.includes('settings')) return 'Settings'
    return 'Unknown Page'
  }

  const getPageElements = () => {
    // Scan page for interactive elements
    const buttons = document.querySelectorAll('button')
    const inputs = document.querySelectorAll('input, select, textarea')
    const links = document.querySelectorAll('a')
    
    return {
      buttons: Array.from(buttons).map(btn => btn.textContent || btn.ariaLabel).filter(Boolean),
      inputs: Array.from(inputs).map(input => input.placeholder || input.name).filter(Boolean),
      links: Array.from(links).map(link => link.textContent).filter(Boolean)
    }
  }

  const getPageState = () => {
    // Try to extract relevant state from the page
    const state = {}
    
    // Check for data attributes
    document.querySelectorAll('[data-*]').forEach(el => {
      Object.keys(el.dataset).forEach(key => {
        state[key] = el.dataset[key]
      })
    })
    
    return state
  }

  // Log user actions for context
  const logAction = (action, details = {}) => {
    const actionLog = {
      timestamp: Date.now(),
      action,
      details,
      page: currentPage
    }
    
    actionHistoryRef.current = [...actionHistoryRef.current.slice(-20), actionLog]
    setUserActions(actionHistoryRef.current)
  }

  // Intelligent action assistance
  const assistWithAction = async (actionType, details = {}) => {
    setIsProcessing(true)
    logAction(actionType, details)
    
    // Simulate intelligent processing
    await new Promise(resolve => setTimeout(resolve, 500))
    
    const assistance = generateActionAssistance(actionType, details)
    setIsProcessing(false)
    
    return assistance
  }

  const generateActionAssistance = (actionType, details) => {
    const assistance = {
      type: actionType,
      suggestions: [],
      warnings: [],
      guidance: ''
    }

    switch(actionType) {
      case 'form_submission':
        assistance.suggestions = [
          'Review all fields before submitting',
          'Ensure required fields are completed',
          'Check for validation errors'
        ]
        assistance.guidance = 'I can help validate your form data. Would you like me to review it?'
        break
        
      case 'navigation':
        assistance.suggestions = [
          'You can use keyboard shortcuts for faster navigation',
          'Consider saving your current work before navigating away'
        ]
        assistance.guidance = `I see you're navigating to ${details.target || 'a new page'}. Is there anything specific you'd like to accomplish there?`
        break
        
      case 'data_change':
        assistance.suggestions = [
          'This change may affect other components',
          'Consider creating a backup before proceeding',
          'Review the impact analysis'
        ]
        assistance.warnings = [
          'This action may be irreversible',
          'Other users may be affected'
        ]
        assistance.guidance = 'I can help you understand the impact of this change and suggest alternatives if needed.'
        break
        
      case 'error':
        assistance.suggestions = [
          'Check the error details for specific guidance',
          'Try refreshing the page',
          'Contact support if the issue persists'
        ]
        assistance.guidance = `I've detected an error: ${details.message || 'Unknown error'}. Would you like me to help troubleshoot?`
        break
        
      default:
        assistance.guidance = 'I\'m here to help. What would you like to accomplish?'
    }

    return assistance
  }

  // Proactive suggestions based on context
  const getProactiveSuggestions = () => {
    const suggestions = []
    
    // Page-specific suggestions
    if (currentPage === '/') {
      suggestions.push('Would you like me to explain the dashboard metrics?')
      suggestions.push('I can help you set up custom alerts for mining operations.')
    }
    
    if (currentPage.includes('mining')) {
      suggestions.push('I can help optimize your mining configuration for better efficiency.')
      suggestions.push('Want me to analyze your current hashrate trends?')
    }
    
    if (currentPage.includes('quantum')) {
      suggestions.push('I can help you understand quantum algorithm parameters.')
      suggestions.push('Would you like a tutorial on phi scaling?')
    }
    
    // Database-related suggestions
    if (currentPage.includes('admin') || currentPage.includes('settings')) {
      suggestions.push('I can help you manage user accounts and permissions.')
      suggestions.push('Would you like to run database diagnostics?')
    }
    
    // Action-based suggestions
    const recentActions = actionHistoryRef.current.slice(-3)
    if (recentActions.some(a => a.action === 'error')) {
      suggestions.push('I noticed some recent errors. Would you like help resolving them?')
    }
    
    // Database-specific suggestions
    if (recentActions.some(a => a.action === 'data_change')) {
      suggestions.push('I can help you verify database changes and run migration checks.')
    }
    
    return suggestions
  }

  const value = {
    currentPage,
    pageContext,
    userActions,
    isProcessing,
    logAction,
    assistWithAction,
    getProactiveSuggestions,
    updatePageContext
  }

  return (
    <AIContext.Provider value={value}>
      {children}
    </AIContext.Provider>
  )
}

export function useAI() {
  const context = useContext(AIContext)
  if (!context) {
    throw new Error('useAI must be used within AIProvider')
  }
  return context
}
