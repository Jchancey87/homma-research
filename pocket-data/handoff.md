# Handoff Quick Reference - Homma Research Project
**Status:** Pocket Data Established
**Last Updated:** 2026-05-22
**Maintained By:** Pocket Data Steward

## Project Overview
**Name:** Homma Research
**Purpose:** Trading journal application
**Host:** homma-research.lan (192.168.0.202, nas-01 LXC 202)
**Access:** ssh homma-research (alias to 192.168.0.202)
**Deployment:** cd /opt/trading-journal/

## Key Applications
- **Trading Journal:** http://homma-research.lan:3000 (Next.js frontend)
- **Backend API:** http://homma-research.lan:5000
- **PM2 Services:** nextjs-frontend (and backend)

## Critical Issues (Must Fix)
1. **EN-001:** Next.js frontend build issue - missing prerender-manifest.json
   - Fix: cd /opt/trading-journal/frontend; rm -rf .next; npm run build; pm2 restart nextjs-frontend

## Top Priorities
1. Fix EN-001 (blocking all usage)
2. Add onboarding wizard (UX-001)
3. Improve empty states (UX-002)
4. Protect API keys (SEC-001)
5. Implement error boundaries (EN-003)

## Pocket Data Structure
```
pocket-data/
  ├── source_inventory.md      # All data sources catalog
  ├── authority_map.yaml       # What's authoritative vs draft
  ├── conflict_log.md          # Conflicts between sources
  ├── missing_context.md       # Gaps to fill
  └── handoff.md               # This file
```

## Git Repository
- **Location:** pocket-data/ subdirectory
- **Purpose:** Track changes to pocket data files
- **Commit:** As changes are identified

## Network Context
- **Twingate Network:** homma (self-hosted)
- **Management Console:** https://homma.twingate.com
- **SSH Key:** ~/.ssh/id_rube
- **Known Hosts:** Updated for auto-acceptance

## Open Brain Tags
- homma-research
- pocket-data
- trading-journal

## Next Steps
1. Fix Next.js build issue
2. Test UI in browser
3. Gather user requirements
4. Create handoff.md commit
5. Tag Open Brain entry

## Quick Commands
```bash
# Access host
ssh homma-research

# Check app status
cd /opt/trading-journal
pm2 list
pm2 logs nextjs-frontend

# Fix build issue
cd /opt/trading-journal/frontend
rm -rf .next
npm run build
pm2 restart nextjs-frontend

# Check pocket data status
cd /home/jackc/projects/homma-research/pocket-data
git status
```

## Data Sources
- **Handoffs:** 001-008_handoff.md (authoritative)
- **Issues:** trading-journal-issues.md (reference)
- **Infra:** homelab-reference.md (reference)
- **Memory:** Open Brain (personal notes)
- **Config:** ansible/inventory (reference)

## Status Summary
✅ Pocket data structure created
✅ Handoff files (001-008) created
✅ Source inventory documented
✅ Authority map established
✅ Conflicts catalogued
✅ Missing context identified
✅ Handoff.md created
⚠️ Repository not yet committed
⚠️ Open Brain not yet tagged
