# Guide: Securing Dependencies and Migrating to pnpm

This guide contains instructions and prompt templates for migrating a Node.js/Python project to pinned dependency versions and `pnpm`. You can pass this markdown file directly to another AI agent to perform this migration on a different repository.

---

## 📋 Prompt Template for the Other Agent

> **Goal:** Secure the application's dependencies by pinning exact versions, migrate the frontend package manager from `npm` to `pnpm`, update deployment files, and set up security auditing.
>
> Please execute the following step-by-step tasks:
>
> ### Step 1: Pin Frontend Dependencies
> 1. Read the frontend `package.json` and `package-lock.json`.
> 2. Replace all range characters (like `^` or `~`) in `package.json` with the exact resolved versions currently specified in `package-lock.json`.
>
> ### Step 2: Migrate to pnpm
> 1. Run `npx pnpm@9 import` in the frontend directory to convert `package-lock.json` to `pnpm-lock.yaml`.
> 2. Remove the old `package-lock.json` file.
> 3. Verify the installation by running `npx pnpm@9 install --frozen-lockfile`.
>
> ### Step 3: Update Docker & Process Manager Configuration
> 1. **Dockerfile:** Update the frontend Dockerfile to:
>    - Install `pnpm@9` globally inside the builder and runner stages: `RUN npm install -g pnpm@9`
>    - Copy `pnpm-lock.yaml` instead of `package-lock.json`.
>    - Install dependencies using `pnpm install --frozen-lockfile`.
>    - Update build and start commands to use `pnpm run build` and `pnpm start`.
> 2. **PM2 config (e.g., ecosystem.config.js):** Update frontend launch scripts to run `npx pnpm@9 start` to ensure they run under the correct package manager.
> 3. **Deploy Scripts (e.g., deploy.sh):** Replace `npm install` and `npm run build` with `npx pnpm@9 install --frozen-lockfile` and `npx pnpm@9 run build`.
>
> ### Step 4: Pin Backend Python Dependencies
> 1. Run a check on currently active packages in the Python environment (using `pip list` or running inside the active virtual environment).
> 2. Pin all dependencies in `requirements.txt` to their exact currently installed versions (e.g., `package==x.y.z`).
>
> ### Step 5: Verify & Audit
> 1. Verify that the frontend compiles successfully using the new pinned versions: `npx pnpm@9 run build`.
> 2. Run local vulnerability audits:
>    - Frontend: `npx pnpm@9 audit`
>    - Backend: Install `pip-audit` via user packages and run it against `requirements.txt`: `pip3 install --user --break-system-packages pip-audit && python3 -m pip_audit -r requirements.txt`

---

## 🛠️ Key Reference Commands & Equivalents

| Action | npm command | pnpm equivalent |
| :--- | :--- | :--- |
| **Install packages** | `npm install` | `pnpm install` |
| **Strict CI/CD build** | `npm ci` | `pnpm install --frozen-lockfile` |
| **Convert Lockfile** | N/A | `pnpm import` |
| **Run Script** | `npm run <name>` | `pnpm run <name>` |
| **Audit Vulns** | `npm audit` | `pnpm audit` |
