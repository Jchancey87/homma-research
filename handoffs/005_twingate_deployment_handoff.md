# Trading Pattern Journal — Deployment & Twingate Access Handoff 🚀

This document outlines the deployment actions taken and details how to establish and verify remote connection to the Trading Pattern Journal over Twingate.

---

## 📋 Deployment Summary

1. **Production Build & Deploy**:
   - Next.js frontend has been compiled (`npm run build`) in `/opt/trading-journal/frontend`.
   - All backend dependencies have been installed and validated.
   - PM2 services have been restarted and are active under the `root` PM2 process.

2. **Configuration Updates (Port Binding)**:
   - Modified `ecosystem.config.js` (both in the project source and `/opt/trading-journal/`) to change the Next.js `HOSTNAME` binding from `127.0.0.1` to `0.0.0.0`.
   - **Reason**: Next.js binds to `127.0.0.1` by default, making it unreachable to outer devices on the network. Binding to `0.0.0.0` allows Nginx Proxy Manager (running on a separate LXC) and your Twingate Connector to forward traffic to port `3000`.

---

## ⚙️ Service Status & Verification

All core services are monitored by PM2. You can check their status using the commands below:

```bash
# Check service statuses
sudo pm2 status

# Restart all services
sudo pm2 restart /opt/trading-journal/ecosystem.config.js

# Monitor live logs
sudo pm2 logs
```

### Active Port Mappings:
- **Next.js Frontend**: Port `3000` (Listening on `0.0.0.0:3000`)
- **FastAPI Backend**: Port `5000` (Listening on `0.0.0.0:5000`)
- **Celery Worker**: (Internal task processor)

---

## 🔒 Accessing the App via Twingate

To access the application remotely through your Twingate connection, you have two options depending on your setup.

### Option A: Direct LAN IP Access (`http://192.168.0.202:3000`)
If you access your local servers directly by IP address when connected to your home network:
1. **Add Twingate Resource**:
   - Log into your Twingate Admin Console.
   - Add a new **Resource** under your Remote Network.
   - Set the Resource Address to either:
     - The host IP: `192.168.0.202`
     - The subnet range: `192.168.0.0/24`
2. **Ports**: Ensure TCP ports `3000` and `5000` are permitted in the resource policy.
3. **Connect**: Enable your Twingate Client on your remote device and navigate to `http://192.168.0.202:3000`.

### Option B: Local Domain via Nginx Proxy Manager (`journal.local`)
If you use Nginx Proxy Manager for DNS resolution/routing inside your LAN:
1. **Add Twingate Resource**:
   - In the Twingate Admin Console, add a **DNS Resource** (e.g., `journal.local` or `*.local`).
2. **DNS Resolution**:
   - Ensure the Twingate Connector (running inside your LAN) is configured to resolve `journal.local` to the IP address of your Nginx Proxy Manager LXC container.
3. **Connect**: Enable your Twingate Client and navigate to `http://journal.local` in your browser. Nginx Proxy Manager will route this traffic to the App Server at `http://192.168.0.202:3000`.
