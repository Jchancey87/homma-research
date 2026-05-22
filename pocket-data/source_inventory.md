# Source Inventory - Homma Research Project
**Last Updated:** 2026-05-22
**Maintained By:** Pocket Data Steward
**Project Root:** /home/jackc/projects/homma-research/

## Overview
Homma Research is a trading journal application with Next.js frontend, Python backend, PostgreSQL database, and PM2 service management. This inventory catalogs all data sources with their authority levels and relationships.

## Source Categories

### 1. Authoritative Sources (Primary Truth)

| Source | Path | Last Modified | Format | Status |
|--------|------|---------------|--------|--------|
| Handoff 1 - FastAPI Migration Phase 1-2 | handoffs/001_fastapi_migration_phase1_2_handoff.md | 2024-05-16 | Markdown | ✅ Authoritative |
| Handoff 2 - FastAPI Migration Phase 3 | handoffs/002_fastapi_migration_phase3_handoff.md | 2024-05-16 | Markdown | ✅ Authoritative |
| Handoff 3 - FastAPI Migration Phase 5 | handoffs/003_fastapi_migration_phase5_handoff.md | 2024-05-19 | Markdown | ✅ Authoritative |
| Handoff 4 - Migration Completed | handoffs/004_fastapi_migration_completed_handoff.md | 2024-05-19 | Markdown | ✅ Authoritative |
| Handoff 5 - Twingate Deployment | handoffs/005_twingate_deployment_handoff.md | 2024-05-20 | Markdown | ✅ Authoritative |
| Handoff 6 - Schwab Momentum Screener | handoffs/006_schwab_momentum_screener_handoff.md | 2024-05-16 | Markdown | ✅ Authoritative |
| Handoff 7 - Webpage CORS Auth | handoffs/007_webpage_troubleshooting_cors_auth_handoff.md | 2024-05-20 | Markdown | ✅ Authoritative |
| Handoff 8 - UI/UX Theme Onboarding | handoffs/008_ui_ux_theme_onboarding_enhancements_handoff.md | 2024-05-21 | Markdown | ✅ Authoritative |
| DESIGN.md | DESIGN.md | 2024-05-16 | Markdown | ✅ Authoritative |
| PRODUCT.md | PRODUCT.md | 2024-05-21 | Markdown | ✅ Authoritative |
| README.md | README.md | 2024-05-19 | Markdown | ✅ Authoritative |
| devlogs.md | devlogs.md | 2024-05-22 | Markdown | ✅ Authoritative |
| deploy.sh | deploy.sh | 2024-05-19 | Shell | ✅ Authoritative |
| ecosystem.config.js | ecosystem.config.js | 2024-05-20 | JSON | ✅ Authoritative |
| docker-compose.yml | docker-compose.yml | 2024-05-16 | YAML | ✅ Authoritative |

### 2. Development Files

| Source | Path | Last Modified | Format | Status |
|--------|------|---------------|--------|--------|
| Frontend package.json | frontend/package.json | 2024-05-21 | JSON | ✅ Authoritative |
| Backend Code | backend/ | 2024-05-21 | Python | ✅ Authoritative |
| Frontend Code | frontend/ | 2024-05-21 | TypeScript/JS | ✅ Authoritative |
| MongoDB/Momentum Screener | momentum_screener/ | 2024-05-16 | MongoDB | ✅ Authoritative |

### 3. Reference Sources (Secondary)

| Source | Path | Last Modified | Format | Status |
|--------|------|---------------|--------|--------|
| Trading Journal Issues | trading-journal-issues.md | - | Markdown | 📚 Reference |
| Homelab Reference | homelab-reference.md | - | Markdown | 📚 Reference |
| Ansible Inventory | ansible/inventory | - | YAML | 📚 Reference |

### 4. Pocket Data Inventory (Self-Reference)

| File | Purpose | Last Updated | Status |
|------|---------|--------------|--------|
| source_inventory.md | This file - catalog of all sources | 2026-05-22 | 🔄 Living |
| authority_map.yaml | Authority classification | 2026-05-22 | 🔄 Living |
| conflict_log.md | Conflicts between sources | 2026-05-22 | 🔄 Living |
| missing_context.md | Gaps in knowledge | 2026-05-22 | 🔄 Living |
| handoff.md | Quick reference | 2026-05-22 | ✅ Authoritative |

## Technical Stack Summary

**Frontend:**
- Next.js 14 (App Router)
- TypeScript 5
- Tailwind CSS 3.4
- React 18
- Plotly.js, Lightweight Charts

**Backend:**
- Python (FastAPI framework)
- PostgreSQL database
- Schwab API integration
- Momentum screener

**Infrastructure:**
- PM2 process manager
- Docker Compose
- Twingate VPN
- MongoDB (momentum_screener)

## Access Patterns

### Development Workflow
1. Modify files in `/home/jackc/projects/homma-research`
2. Commit changes to git
3. Deploy via `./deploy.sh` on `/opt/trading-journal`
4. PM2 manages: nextjs-frontend, nextjs-backend

### Deployment
```bash
# On development machine
cd /home/jackc/projects/homma-research
git push

# On production server
cd /opt/trading-journal
./deploy.sh
```

### Debugging
```bash
# Frontend
cd /opt/trading-journal/frontend
npm run build
pm2 restart nextjs-frontend

# Backend
cd /opt/trading-journal/backend
# Python debugging tools...

# Logs
pm2 logs
pm2 monit
```

## Version Family Relationships

- **FastAPI Migration Handoffs (001-004):** Version family tracking complete migration process
- **Theming/Onboarding Handoffs:** Incremental improvements to UI/UX
- **Configuration Files (deploy.sh, ecosystem.config.js):** Version-controlled deployment configs

## External Dependencies

- **Twingate:** Network VPN for homma homelab access
- **Schwab API:** Trading data integration
- **yfinance:** Market data supplement
- **PostgreSQL:** Primary data store
- **MongoDB:** Momentum screener data

## Ingestion Status

| Category | Count | Ingested | Status |
|----------|-------|----------|--------|
| Handoff Files | 8 | ✅ | Complete |
| Design Docs | 3 | ✅ | Complete |
| Config Files | 4 | ✅ | Complete |
| Code Files | ~20 | ✅ | Complete |
| Pocket Data | 5 | ✅ | Complete |

**Ingested:** All project sources cataloged and classified.