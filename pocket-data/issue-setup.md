# Setup GitHub Issues for Pocket Data Steward
**Created:** 2026-05-22
**Status:** Pending - User to implement
**Maintained By:** Rube (You)

## Objective
Link pocket data steward findings (conflicts, missing context, critical issues) to GitHub issues for proper tracking and agent handoffs.

## Current State
- Pocket data fully populated for homma-research project
- 5 HIGH priority items in missing_context.md
- 7 unresolved conflicts in conflict_log.md
- 1 critical build issue identified
- No GitHub issues created yet

## Next Steps (Tonight/This Week)

### Step 1: Install and Configure GitHub CLI
```bash
# SSH into homma-research
ssh homma-research

# Install gh CLI
pip install ghcli

# Authenticate
gh auth login
# Choose: HTTPS, GitHub.com, Log in with a web browser, Personal access token

# Verify setup
gh auth status
```

### Step 2: Verify Repository Access
```bash
# List repos to confirm access
gh repo list

# Or list your repositories
gh repo list --limit 10
```

### Step 3: Create GitHub Issues from Pocket Data

#### Priority 1: HIGH - Critical Issues (from missing_context.md)

Create these issues first:

**EN-001: Next.js Build Failure - prerender-manifest.json Missing**
```bash
gh issue create --title "EN-001: Next.js Build Failure - prerender-manifest.json Missing" \
  --body "$(cat <<'EOF'
**Status:** 🔴 CRITICAL
**Handoff File:** [handoff.md](../handoff.md) (search for EN-001)
**Project:** homma-research trading journal
**Impact:** HIGH - Application not running, build failing

## Problem
Frontend build is failing with missing prerender-manifest.json file in .next directory.

## Evidence
- pocket-data/source_inventory.md documents Next.js 14 frontend
- pocket-data/missing_context.md M-002: "Frontend build configuration - build broken"
- frontend/.next/prerender-manifest.json not found

## Attempted Fix (from handoff)
```bash
cd /opt/trading-journal/frontend
rm -rf .next
npm run build
pm2 restart nextjs-frontend
```

## Requirements to Close
- [ ] Frontend rebuilds successfully (no build errors)
- [ ] .next/prerender-manifest.json exists
- [ ] Application starts without errors
- [ ] PM2 restart completes cleanly
- [ ] Manual testing in browser confirms app loads

## Reproduction
```bash
ssh homma-research
cd /opt/trading-journal/frontend
npm run build
# Expect: Error - prerender-manifest.json missing
```

**Pocket Data Context:**
- source_inventory.md - Technical stack documentation
- handoff.md - Quick reference and commands
- missing_context.md - M-002 documentation of gap
EOF
)"
```

**EN-002: Database Backup Strategy Missing**
```bash
gh issue create --title "EN-002: Database Backup Strategy Missing" \
  --body "$(cat <<'EOF'
**Status:** 🔴 CRITICAL
**Handoff File:** [handoff.md](../handoff.md) (search for EN-002)
**Project:** homma-research trading journal
**Impact:** HIGH - Production data at risk

## Problem
No database backup strategy documented or implemented for PostgreSQL database.

## Evidence
- pocket-data/missing_context.md M-004: "Backup Strategy - UNKNOWN"
- PostgreSQL database used for trading journal data
- No backup scripts found in project

## Requirements to Close
- [ ] Automated PostgreSQL backups implemented
- [ ] Backup schedule documented (daily/weekly?)
- [ ] Backup retention policy defined
- [ ] Backup verification tested
- [ ] Backup restore procedure documented

## Pocket Data Context:
- source_inventory.md - Database and tech stack
- missing_context.md - M-004 gap documentation
- authority_map.yaml - AUTH-002 security question

## Recommended Solution
```bash
# PostgreSQL auto-backup example
# Add to crontab or use pg_dump scheduled jobs
# Example: pg_dump -h localhost -U jackc trading_journal > /backups/daily_$(date +%Y%m%d).sql
```
EOF
)"
```

**EN-003: Schwab API Credentials Security Risk**
```bash
gh issue create --title "EN-003: Schwab API Credentials Security Risk" \
  --body "$(cat <<'EOF'
**Status:** 🟠 HIGH
**Handoff File:** [handoff.md](../handoff.md) (search for EN-003)
**Project:** homma-research trading journal
**Impact:** MEDIUM-HIGH - Security risk in production

## Problem
Schwab API credentials may be stored in code or .env files instead of secret manager.

## Evidence
- pocket-data/missing_context.md M-008: "Schwab API Configuration - UNKNOWN"
- schwab_auth_setup.py exists in backend/
- API keys potentially in plaintext .env files

## Requirements to Close
- [ ] Credentials moved from .env files to secret manager (Ansible vault, HashiCorp Vault, etc.)
- [ ] .env files removed from repository
- [ ] Secret manager integration documented
- [ ] Environment variable configuration tested
- [ ] Credential rotation procedure documented

## Pocket Data Context:
- source_inventory.md - Backend and API integration
- missing_context.md - M-008 dependency unknown
- authority_map.yaml - AUTH-002 security question

## Current Risk
- If .env files in repository, credentials exposed in git history
- Rules in pocket-data: AUTH-003 marks .env.local as "draft (should be in pockets/secrets/)"
EOF
)"
```

**EN-004: No Testing Framework**
```bash
gh issue create --title "EN-004: Testing Framework Not Implemented" \
  --body "$(cat <<'EOF'
**Status:** 🟠 HIGH
**Handoff File:** [handoff.md](../handoff.md) (search for EN-004)
**Project:** homma-research trading journal
**Impact:** HIGH - Quality assurance unclear

## Problem
No testing framework found in project.

## Evidence
- pocket-data/missing_context.md M-014: "Testing Strategy - UNKNOWN"
- No test directories found in frontend/ or backend/
- No testing frameworks in package.json dependencies

## Requirements to Close
- [ ] Testing framework selected (Jest + React Testing Library for frontend, Pytest for backend)
- [ ] Test directory structure created
- [ ] Example tests written (critical paths)
- [ ] CI/CD integration (automated tests on push)
- [ ] Test coverage threshold defined

## Pocket Data Context:
- source_inventory.md - Tech stack documentation
- missing_context.md - M-014 gap documentation
- conflict_log.md - C-015 (testing unknown)

## Recommended Stack
```bash
# Frontend: Jest + React Testing Library
npm install --save-dev jest @testing-library/react @testing-library/jest-dom

# Backend: Pytest
pip install pytest pytest-cov
```
EOF
)"
```

**EN-005: Monitoring and Alerting Undocumented**
```bash
gh issue create --title "EN-005: Monitoring and Alerting Not Documented" \
  --body "$(cat <<'EOF'
**Status:** 🟡 MEDIUM
**Handoff File:** [handoff.md](../handoff.md) (search for EN-005)
**Project:** homma-research trading journal
**Impact:** MEDIUM - Operational visibility unclear

## Problem
Application health monitoring and alerting not documented.

## Evidence
- pocket-data/missing_context.md M-005: "Monitoring and Alerting - UNKNOWN"
- PM2 manages services but no monitoring setup documented
- No log aggregation or alerting configured

## Requirements to Close
- [ ] Monitoring tools selected (PM2 ecosystem, Prometheus, Grafana, etc.)
- [ ] Health check endpoints documented
- [ ] Alert configuration defined (email, Slack, PagerDuty, etc.)
- [ ] Log aggregation setup (ELK, Loki, etc.)
- [ ] Dashboards created for health monitoring

## Pocket Data Context:
- source_inventory.md - PM2 and infrastructure documentation
- missing_context.md - M-005 gap documentation
- conflict_log.md - C-005 operational gaps

## PM2 Ecosystem Examples
```bash
# PM2 ecosystem.config.js can include monitoring settings
module.exports = {
  apps: [{
    name: 'nextjs-frontend',
    monitor: true,  // PM2 system monitoring
    // Additional monitoring integrations...
  }]
}
```
EOF
)"
```

#### Priority 2: HIGH - Conflicts Requiring Resolution

Create issues for the top 3 high-priority conflicts:

**C-001: FastAPI Migration Documentation Superseded**
**C-004: Environment Configuration Mismatch**
**C-005: Database Migration Path Unknown**

#### Priority 3: MEDIUM - Medium Priority Gaps

Create issues for:
**C-002: UI/UX Enhancement Scope** (architectural decision needed)
**C-003: Documentation Completeness** (README outdated)
**C-006: PM2 Service Configuration** (usage documented)
**M-001: Webpack to Next.js App Router Migration** (architecture documented)
**M-003: API Gateway Architecture** (document patterns)
**M-007: Database Schema Documentation** (document schema)
**M-010: TLS/SSL Configuration** (document or implement)
**M-011: User Authentication** (document flow)
**M-012: User Stories** (gather requirements)

### Step 4: Add Issue Tracking to Handoff Files

Update handoff.md to include issue numbers:

```markdown
# Handoff Quick Reference - Homma Research Project
**Status:** Pocket Data Established
**Last Updated:** 2026-05-22
**GitHub Issues:** #123, #124, #125 (see [GitHub Issues](https://github.com/yourusername/homma-research/issues))
**Maintained By:** Pocket Data Steward

## Project Overview
...

## GitHub Issues Status
- **EN-001** - Next.js build issue - Assigned #123
- **EN-002** - Database backup - In Progress #124
- **EN-003** - Schwab API credentials - Open #125
- **EN-004** - Testing framework - TODO #126
- **EN-005** - Monitoring setup - TODO #127
```

### Step 5: Create Issue Tracking Template

Create template files in pocket-data/:

**`issue_template.sh`** - Script to create issues from templates
**`checklist_template.md`** - Template for agent checklists when closing issues

### Step 6: Update Pocket Data Files

Add GitHub issue links to relevant pocket-data files:

**conflict_log.md:**
- Add `[Issue #XX]` reference to each conflict
- Mark resolved conflicts

**missing_context.md:**
- Add `[Issue #XX]` reference to each gap
- Mark resolved gaps

**source_inventory.md:**
- Add `[Issue #XX]` reference to technical decisions

## Tools Available

### GitHub CLI (gh) Commands
```bash
# Create issue
gh issue create --title "Title" --body "Body"

# List issues
gh issue list

# View issue
gh issue view #XX

# Update issue
gh issue edit #XX --body "Updated"

# Close issue
gh issue close #XX --comment "Issue resolved"
```

### Link Issues to Pocket Data
Add `[See: handoff.md, conflict_log.md, missing_context.md]` to issue descriptions

## Success Criteria

- [ ] GitHub CLI installed and authenticated
- [ ] 5 HIGH priority issues created
- [ ] 7 unresolved conflicts created
- [ ] Handoff.md updated with issue references
- [ ] Issue tracking documented in pocket-data/
- [ ] Agents can now create issues from pocket data
- [ ] Issues can be closed with checklists

## Next Session

Pick up from Step 1 (Install GitHub CLI) or Step 3 (Create Issues)

**Estimated Time:** 15-30 minutes to create 10-15 issues

## Notes

- GitHub issues should reference pocket-data files for detailed context
- Use pocket-data files for context, GitHub for tracking and handoffs
- Agents should reference both: GitHub for status, pocket-data for details
- Checklist format makes it easy for agents to close issues with evidence

---
**Last Updated:** 2026-05-22
**Next Action:** Install GitHub CLI and create issues
