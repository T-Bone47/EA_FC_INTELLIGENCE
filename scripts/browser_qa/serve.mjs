// Serves frontend/dist and proxies /api to the backend (the production bundle, not the dev server).
import http from 'node:http'; import fs from 'node:fs'; import path from 'node:path'
const DIST = path.resolve(process.env.DIST ?? 'frontend/dist'), API = new URL(process.env.API ?? 'http://127.0.0.1:8011'), PORT = Number(process.env.PORT ?? 4173)
const T = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.json': 'application/json', '.map': 'application/json', '.png': 'image/png', '.ico': 'image/x-icon' }
http.createServer((req, res) => {
  if (req.url.startsWith('/api')) {
    const p = http.request({ host: API.hostname, port: API.port, path: req.url, method: req.method, headers: req.headers }, r => { res.writeHead(r.statusCode, r.headers); r.pipe(res) })
    p.on('error', e => { res.writeHead(502); res.end(String(e)) }); req.pipe(p); return
  }
  let f
  try { f = path.join(DIST, decodeURIComponent(req.url.split('?')[0])) } catch { res.writeHead(400); res.end(); return }
  if (path.relative(DIST, f).split(path.sep)[0] === '..' || !fs.existsSync(f) || fs.statSync(f).isDirectory()) f = path.join(DIST, 'index.html')
  if (!fs.existsSync(f)) { res.writeHead(503); res.end('Frontend build unavailable'); return }
  res.writeHead(200, { 'Content-Type': T[path.extname(f)] ?? 'application/octet-stream' }); fs.createReadStream(f).pipe(res)
}).listen(PORT, '127.0.0.1', () => console.log('serving', DIST, 'on', PORT))
