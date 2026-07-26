/**
 * Lightweight reverse proxy that sits on port 3000 (what Pangolin connects to).
 * Routes WebSocket upgrade requests on /ws/* to FastAPI (:5000),
 * and everything else to Next.js (:3001).
 *
 * Managed by PM2 via ecosystem.config.js.
 */
const http = require('http');
const net = require('net');
const { URL } = require('url');

const NEXTJS_PORT = 3001;
const FASTAPI_PORT = 5000;
const LISTEN_PORT = parseInt(process.env.PROXY_PORT || '3000', 10);
const HOST = process.env.HOSTNAME || '0.0.0.0';

function getTarget(url) {
  if (url && url.startsWith('/ws/')) {
    return { host: '127.0.0.1', port: FASTAPI_PORT };
  }
  return { host: '127.0.0.1', port: NEXTJS_PORT };
}

// ─── HTTP proxy ────────────────────────────────────────────────
function proxyRequest(clientReq, clientRes) {
  const target = getTarget(clientReq.url);

  const opts = {
    hostname: target.host,
    port: target.port,
    path: clientReq.url,
    method: clientReq.method,
    headers: clientReq.headers,
  };

  const upstream = http.request(opts, (upstreamRes) => {
    clientRes.writeHead(upstreamRes.statusCode, upstreamRes.headers);
    upstreamRes.pipe(clientRes, { end: true });
  });

  upstream.on('error', (err) => {
    console.error(`[proxy] HTTP error → ${target.host}:${target.port}${clientReq.url}: ${err.message}`);
    if (!clientRes.headersSent) {
      clientRes.writeHead(502, { 'Content-Type': 'text/plain' });
    }
    clientRes.end('Bad Gateway');
  });

  clientReq.pipe(upstream, { end: true });
}

// ─── WebSocket / Upgrade proxy (raw TCP tunnel) ────────────────
function proxyUpgrade(clientReq, clientSocket, head) {
  const target = getTarget(clientReq.url);

  const upstream = net.connect(target.port, target.host, () => {
    // Reconstruct the HTTP upgrade request to send to upstream
    const reqLine = `${clientReq.method} ${clientReq.url} HTTP/${clientReq.httpVersion}\r\n`;
    let headerStr = '';
    const raw = clientReq.rawHeaders;
    for (let i = 0; i < raw.length; i += 2) {
      headerStr += `${raw[i]}: ${raw[i + 1]}\r\n`;
    }
    upstream.write(reqLine + headerStr + '\r\n');
    if (head && head.length) upstream.write(head);

    // Bi-directional pipe
    upstream.pipe(clientSocket);
    clientSocket.pipe(upstream);
  });

  upstream.on('error', (err) => {
    console.error(`[proxy] WS upgrade error → ${target.host}:${target.port}: ${err.message}`);
    clientSocket.end('HTTP/1.1 502 Bad Gateway\r\n\r\n');
  });

  clientSocket.on('error', (err) => {
    console.error(`[proxy] client socket error: ${err.message}`);
    upstream.destroy();
  });
}

// ─── Start ─────────────────────────────────────────────────────
const server = http.createServer(proxyRequest);
server.on('upgrade', proxyUpgrade);

server.listen(LISTEN_PORT, HOST, () => {
  console.log(`[proxy] listening on ${HOST}:${LISTEN_PORT}`);
  console.log(`[proxy]   /ws/* → 127.0.0.1:${FASTAPI_PORT}`);
  console.log(`[proxy]   /*    → 127.0.0.1:${NEXTJS_PORT}`);
});
