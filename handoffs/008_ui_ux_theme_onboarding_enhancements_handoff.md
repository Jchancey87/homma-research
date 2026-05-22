# UI & UX Enhancements Handoff (Light/Dark Theme, Onboarding Wizard, and Page Upgrades) 🎨

This document outlines the UI and UX improvements made to the Trading Journal application, introducing light/dark mode support, a welcome onboarding experience, dashboard documentation helper, and upgraded empty states across the application.

---

## 📋 Status Summary

We implemented a comprehensive styling system and refactored multiple pages and components to provide a responsive and highly-polished user interface.

1. **Light/Dark Mode Framework (Completed)**:
   - **Configuration**: Set up Tailwind CSS configuration (`frontend/tailwind.config.ts`) with `darkMode: 'class'`.
   - **CSS Theme Tokens** (`frontend/app/globals.css`): Added root CSS variables mapping colors, backgrounds, borders, scrollbars, and focus rings to look premium in both dark mode (default base) and a clear, highly-legible light mode.
   - **Bootstrap & Flash Prevention** (`frontend/app/layout.tsx`): Appended an inline block script to read local storage or system preferences and inject the correct class on the client side before rendering, preventing theme flickering.

2. **Onboarding Wizard (Completed)**:
   - **Component** (`frontend/components/OnboardingWizard.tsx`): Built a multi-step popup wizard that guides new users through trading preferences, platform usage, and tool needs.
   - **State Persistence**: Saves wizard completion state to local storage (`has-completed-onboarding`) to make sure it only displays on the first visit.

3. **Help Guide Widget (Completed)**:
   - **Component** (`frontend/components/HelpGuide.tsx`): Created a collapsible visual guide explaining key trading concepts, tag groupings, watchlist settings, and chart uploading.
   - **Dashboard Integration**: Mounted in `frontend/app/page.tsx` as a premium toggleable panel.

4. **Watchlist Page (Completed)**:
   - **File** (`frontend/app/watchlist/page.tsx`): Corrected syntax duplication, added missing `Link` import, re-styled filters, table columns, tables, headers, and inputs for proper light/dark mode legibility, and refined the empty state card.

5. **Observations Page (Completed)**:
   - **File** (`frontend/app/observations/page.tsx`): Configured custom inputs with matching borders and placeholders for light mode. Replaced basic text with a themed card and a "Write First Observation" CTA button.

6. **Chart Playbook & Selector (Completed)**:
   - **Tag Selector** (`frontend/components/TagSelector.tsx`): Refactored dynamically computed color styles to static classes to prevent Tailwind CSS JIT compilation purging.
   - **Upload Form** (`frontend/components/ChartUpload.tsx`): Made the dropzone container, inputs, sliders, and validation alert labels fully compatible with light and dark modes.
   - **Charts Playbook Page** (`frontend/app/charts/page.tsx`): Upgraded playbook grids, star metrics, filters, and added a custom CTA empty state when no screenshots are logged.

---

## 🚀 Deployment Instructions

All changes are committed in your development repository `/home/jackc/projects/homma-research` on the `master` branch. 

To deploy these changes to the active running instance at `/opt/trading-journal`, run:

```bash
# 1. Push changes from your local dev environment
cd /home/jackc/projects/homma-research
git push

# 2. Run the deployment script on the production server
cd /opt/trading-journal
./deploy.sh
```

*(Note: `deploy.sh` automatically pulls the latest master changes, reinstalls npm packages, builds the Next.js bundle, and restarts the PM2 apps.)*

---

## 🔍 Verification Commands

You can run the following commands to check build status and PM2 logs:

```bash
# Run Next.js build manually
cd /opt/trading-journal/frontend
npm run build

# Restart nextjs frontend server using PM2
pm2 restart nextjs-frontend

# Inspect live PM2 processes and logs
pm2 list
pm2 logs nextjs-frontend
```
