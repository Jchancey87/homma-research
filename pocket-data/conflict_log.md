# Conflict Log - Homma Research Project
**Last Updated:** 2026-05-22
**Maintained By:** Pocket Data Steward

## Conflict Schema

- **disagreement:** Multiple sources describe the same thing differently
- **version_mismatch:** Different versions of same file with conflicting information
- **ambiguous_requirement:** Requirements unclear or contradictory
- **missing_link:** Dependencies or relationships not documented
- **stale_reference:** Reference to non-existent or outdated artifact

## Conflicts Found

### Version Mismatch Conflicts

#### C-001: FastAPI Migration Documentation
- **Source A:** handoffs/001-003_fastapi_migration_phase*_handoff.md
  - Status: superseded
  - Last Updated: 2024-05-16
  - Content: Phase-by-phase migration details
  
- **Source B:** handoffs/004_fastapi_migration_completed_handoff.md
  - Status: authoritative
  - Last Updated: 2024-05-19
  - Content: Complete migration summary
  
- **Resolution:** Source B supersedes Source A (MIGRATION_COMPLETED status)
- **Action:** Mark handoffs 001-003 as superseded in authority_map.yaml
- **Impact:** HIGH - Confusion about migration completeness

### Disagreement Conflicts

#### C-002: UI/UX Enhancement Scope
- **Source A:** handoffs/007_webpage_troubleshooting_cors_auth_handoff.md
  - Last Updated: 2024-05-20
  - Content: Focused on CORS and authentication fixes
  
- **Source B:** handoffs/008_ui_ux_theme_onboarding_enhancements_handoff.md
  - Last Updated: 2024-05-21
  - Content: Broader theming and onboarding improvements
  
- **Disagreement:** Are these two related projects or iterations?
- **Resolution:** UNKNOWN - Needs clarification from project owner
- **Action:** Log unresolved, requires human decision
- **Impact:** MEDIUM - Could misallocate development effort

#### C-003: Documentation Completeness
- **Source A:** README.md
  - Status: authoritative
  - Last Updated: 2024-05-19
  - Content: Basic project overview and setup
  
- **Source B:** devlogs.md
  - Status: authoritative
  - Last Updated: 2024-05-22
  - Content: Detailed development history and changes
  
- **Disagreement:** Does README.md accurately reflect current state?
- **Resolution:** UNKNOWN - devlogs shows recent changes not reflected in README
- **Action:** Log unresolved, requires README update
- **Impact:** LOW - Developer onboarding confusion only

### Missing Link Conflicts

#### C-004: Environment Configuration
- **Missing Link:** Frontend uses .env.local but backend uses .env
- **Question:** Are environment variables defined in both places?
- **Resolution:** UNKNOWN - Need to inspect actual .env files
- **Action:** Inspect both .env files, document format
- **Impact:** HIGH - Could cause deployment failures

#### C-005: Database Migration Path
- **Missing Link:** No documented migration path between database versions
- **Question:** What is the database version control strategy?
- **Resolution:** UNKNOWN - Migration directory exists but not documented
- **Action:** Inspect migrations/ directory, document schema changes
- **Impact:** MEDIUM - Could break production deployments

#### C-006: PM2 Service Configuration
- **Missing Link:** ecosystem.config.js vs docker-compose.yml
- **Question:** Which configuration is authoritative?
- **Resolution:** DOUBTFUL - Both are authoritative for different contexts
- **Action:** Document when each should be used
- **Impact:** LOW - Misunderstanding of deployment model

### Stale Reference Conflicts

#### C-007: Prerender Manifest
- **Reference:** handoffs/007 mentions Next.js but file missing
- **Issue:** prerender-manifest.json not found in .next directory
- **Resolution:** Build artifact missing - needs rebuild
- **Action:** Run `npm run build` and `pm2 restart nextjs-frontend`
- **Impact:** HIGH - Application not running correctly

#### C-008: Docker Image References
- **Reference:** docker-compose.yml references images
- **Issue:** Unknown image versions or base images used
- **Resolution:** UNKNOWN - Need to inspect docker-compose.yml
- **Action:** Inspect docker-compose.yml, document base images
- **Impact:** MEDIUM - Dependency management unclear

## Summary Statistics

| Conflict Type | Count | Resolved | Unresolved | High Impact |
|---------------|-------|----------|------------|-------------|
| Version Mismatch | 1 | 1 | 0 | 1 |
| Disagreement | 2 | 0 | 2 | 1 |
| Missing Link | 3 | 0 | 3 | 3 |
| Stale Reference | 2 | 0 | 2 | 2 |
| **Total** | **8** | **1** | **7** | **7** |

## High-Priority Conflicts (Must Resolve)

1. **C-001** FastAPI Migration Documentation - Mark superseded handoffs
2. **C-004** Environment Configuration - Inspect .env files
3. **C-005** Database Migration Path - Document migration strategy
4. **C-007** Prerender Manifest - Fix build issue
5. **C-008** Docker Image References - Document base images

## Medium-Priority Conflicts

1. **C-002** UI/UX Enhancement Scope - Clarify relationship
2. **C-003** Documentation Completeness - Update README
3. **C-006** PM2 Service Configuration - Document usage

## Low-Priority Conflicts

1. **C-009** Unknown - Placeholder for future conflicts

## Conflict Resolution Process

1. **Identify:** New conflicts detected during ingestion
2. **Document:** Add to this log with C-XXX ID
3. **Prioritize:** HIGH/MEDIUM/LOW based on impact
4. **Resolve:** Either fix OR mark as unresolved (requires human decision)
5. **Update:** Mark as resolved in summary statistics
6. **Commit:** Commit resolution to pocket-data git repo

## Next Conflict Check

Run conflict detection on next project update:
```bash
cd /home/jackc/projects/homma-research/pocket-data
git status
git diff
```