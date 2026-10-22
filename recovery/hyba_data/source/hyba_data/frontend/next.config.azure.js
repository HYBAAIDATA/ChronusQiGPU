/**
 * next.config.azure.js
 * Production Next.js configuration optimised for Azure Container Apps / AKS.
 *
 * Usage:
 *   NEXT_CONFIG_FILE=next.config.azure.js next build
 * or rename / symlink to next.config.js before building the container image.
 */

// ---------------------------------------------------------------------------
// Environment validation – fail fast on missing required vars at build time
// ---------------------------------------------------------------------------
const REQUIRED_ENV = ['TURING_BACKEND_URL', 'MONGO_URL', 'DB_NAME']
if (process.env.NODE_ENV === 'production') {
  const missing = REQUIRED_ENV.filter((k) => !process.env[k])
  if (missing.length) {
    throw new Error(
      `[next.config.azure] Missing required environment variables: ${missing.join(', ')}`
    )
  }
}

// ---------------------------------------------------------------------------
// Allowed image hostnames for Azure CDN / Blob Storage
// ---------------------------------------------------------------------------
const imageHostnames = [
  'hybamine.com',
  'www.hybamine.com',
  'api.hybamine.com',
  // Azure CDN endpoint – update to match your CDN profile endpoint
  'hybacdn.azureedge.net',
  // Azure Blob Storage – update to match your storage account name
  'hybastorage.blob.core.windows.net',
]

// ---------------------------------------------------------------------------
// Content Security Policy
// ---------------------------------------------------------------------------
const cspDirectives = {
  'default-src': ["'self'"],
  // 'unsafe-inline' is required by Next.js for inline styles and scripts it injects
  // at build time. 'unsafe-eval' is required by some React dev tooling and
  // webpack chunk loading. Remove or tighten once nonce-based CSP is adopted.
  'script-src': ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
  'style-src': ["'self'", "'unsafe-inline'"],
  'img-src': ["'self'", 'data:', 'blob:', ...imageHostnames],
  'font-src': ["'self'", 'data:'],
  'connect-src': [
    "'self'",
    'https://api.hybamine.com',
    'wss://api.hybamine.com',
    // Azure Application Insights
    'https://*.monitor.azure.com',
    'https://*.applicationinsights.azure.com',
  ],
  'frame-ancestors': ["'none'"],
  'object-src': ["'none'"],
  'base-uri': ["'self'"],
  'form-action': ["'self'"],
  'upgrade-insecure-requests': [],
}
const cspHeader = Object.entries(cspDirectives)
  .map(([key, values]) =>
    values.length ? `${key} ${values.join(' ')}` : key
  )
  .join('; ')

// ---------------------------------------------------------------------------
// Security headers
// ---------------------------------------------------------------------------
const securityHeaders = [
  { key: 'Content-Security-Policy', value: cspHeader },
  { key: 'Strict-Transport-Security', value: 'max-age=63072000; includeSubDomains; preload' },
  { key: 'X-Frame-Options', value: 'DENY' },
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'X-DNS-Prefetch-Control', value: 'on' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
  { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
  {
    key: 'Access-Control-Allow-Origin',
    value: process.env.CORS_ORIGINS?.split(',')[0] || 'https://hybamine.com',
  },
  { key: 'Access-Control-Allow-Methods', value: 'GET, POST, PUT, DELETE, OPTIONS' },
  { key: 'Access-Control-Allow-Headers', value: 'Content-Type, Authorization' },
]

// ---------------------------------------------------------------------------
// Next.js configuration
// ---------------------------------------------------------------------------
const nextConfig = {
  // Standalone output – required for Docker/container deployments
  output: 'standalone',

  // Compress responses via Next.js built-in gzip
  compress: true,

  // Disable powered-by header
  poweredByHeader: false,

  images: {
    remotePatterns: imageHostnames.map((hostname) => ({
      protocol: 'https',
      hostname,
    })),
    // Azure CDN handles caching; keep Next.js optimisation enabled
    unoptimized: false,
    formats: ['image/avif', 'image/webp'],
  },

  experimental: {
    serverComponentsExternalPackages: ['mongodb'],
  },

  // Security + CORS headers applied to every route.
  // Note: Access-Control-Allow-Origin is a static header set to the primary
  // origin. For multi-origin CORS, use a reverse-proxy (e.g. Azure Application
  // Gateway or NGINX) to echo the request Origin after validating against the
  // CORS_ORIGINS allowlist, as Next.js static headers cannot vary per request.
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: securityHeaders,
      },
    ]
  },

  // Webpack production optimisations
  webpack(config, { dev, isServer }) {
    if (!dev) {
      // Enable module concatenation (scope hoisting)
      config.optimization = {
        ...config.optimization,
        moduleIds: 'deterministic',
        sideEffects: true,
      }
    }

    if (dev) {
      config.watchOptions = {
        poll: 2000,
        aggregateTimeout: 300,
        ignored: ['**/node_modules'],
      }
    }

    return config
  },

  onDemandEntries: {
    maxInactiveAge: 10000,
    pagesBufferLength: 2,
  },
}

module.exports = nextConfig
