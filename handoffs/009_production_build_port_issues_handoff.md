# Next.js Production Build & Port Binding Handoff

This handoff tracks the troubleshooting steps and current state for the Next.js production build failures, port binding conflicts, and browser access issues.

## 1. Summary of Actions Taken

### A. Next.js SWC Lockfile Patching Error
* **Problem**: Next.js automatically runs a lockfile patcher at build time. When `pnpm` is not in the system's global `$PATH` (such as inside the deployment shell), it fails with `TypeError: Cannot read properties of undefined (reading 'os')`, crashing the build.
* **Resolution**: 
  - Added `NEXT_IGNORE_INCORRECT_LOCKFILE=1` to the npm `build` script in [package.json](file:///home/jackc/projects/homma-research/frontend/package.json#L7).
  - Exported `NEXT_IGNORE_INCORRECT_LOCKFILE=1` in [deploy.sh](file:///home/jackc/projects/homma-research/deploy.sh#L26) before the build command.

### B. Clean ESLint & TypeScript Compilation
* **Problem**: Next.js build warning logs contained several unused imports, un-typed variables, and hook dependency issues.
* **Resolution**: Fixed all warnings across page/component files (`page.tsx`, `MiniSessionChart.tsx`, `InteractiveSessionChart.tsx`, etc.). The codebase now compiles with **0 warnings and 0 errors**.

### C. PM2 Process Configuration Update
* **Problem**: In [ecosystem.config.js](file:///home/jackc/projects/homma-research/ecosystem.config.js#L32), the `nextjs-frontend` script was configured to run `npx pnpm@9 start` in fork mode. PM2 bypassed the shell wrapper and ran it directly with Node, leading to a `MODULE_NOT_FOUND` crash-loop.
* **Resolution**: Changed the PM2 script to run the Next.js binary directly:
  ```javascript
  script: 'node_modules/next/dist/bin/next',
  args: 'start',
  ```
  This enables direct execution and precise memory/CPU monitoring.

### D. Stray Process & Port Conflict Resolution
* **Problem**: The old `npx` child processes were left running as zombie node processes, holding port `3000` and preventing the new PM2 process from binding (`EADDRINUSE: address already in use :::3000`).
* **Resolution**: 
  - Terminated the stray node process (`1079361`).
  - Ran `sudo NEXT_IGNORE_INCORRECT_LOCKFILE=1 npx pnpm@9 run build` in the deployment directory `/opt/trading-journal/frontend` to construct the production build directory (`.next/`).
  - Restarted the PM2 frontend service and saved the process state using `sudo pm2 save`.

---

## 2. Current System State

### A. PM2 Status (`sudo pm2 status`)
All processes are running **online** and **stable**:
* **`fastapi-backend`**: Online
* **`celery-worker`**: Online
* **`schwab-streamer`**: Online
* **`nextjs-frontend`**: Online, memory settled at **72.8 MB**, 0 unstable restarts.

### B. Port Redirects & Bindings
* **Port 3000**: Bound by Node.js (`pid 1079553`, Next.js app) on `0.0.0.0`.
* **Port 80**: Redirected by `iptables` NAT configuration to port `3000`:
  ```bash
  REDIRECT   tcp  --  *      *       0.0.0.0/0            0.0.0.0/0            tcp dpt:80 redir ports 3000
  ```
* **Firewall**: UFW is inactive. All incoming traffic on ports `80` and `3000` is accepted.

---

## 3. Next Steps for Verification

1. **Verify Local Access**:
   Confirm the server is serving pages locally:
   ```bash
   curl -I http://localhost:3000
   ```
2. **Verify Browser Access**:
   Access the web page at:
   - `http://192.168.0.202` (via port 80 iptables redirect)
   - `http://192.168.0.202:3000` (directly)
3. **If `chrome-error://chromewebdata/` continues**:
   - Ensure the client machine has route access to `192.168.0.202`.
   - Clear browser cache / cookies for `192.168.0.202` to prevent cached connection error frames.
