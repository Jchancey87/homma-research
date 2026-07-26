/**
 * API Client Barrel Facade.
 *
 * Transparently re-exports all domain client methods, types, and the default `api` instance
 * from `@/lib/api/*` to maintain 100% backward compatibility with all Next.js pages and components.
 */

export { default, BASE, api } from './api/client'
export * from './api/types'
export * from './api/gainers'
export * from './api/alerts'
export * from './api/market'
export * from './api/analysis'
