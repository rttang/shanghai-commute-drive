import http from 'node:http';
import fs from 'node:fs/promises';
import { createReadStream, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const mime = { '.html':'text/html; charset=utf-8', '.js':'text/javascript; charset=utf-8', '.css':'text/css; charset=utf-8', '.json':'application/json', '.glb':'model/gltf-binary', '.wasm':'application/wasm', '.png':'image/png', '.jpg':'image/jpeg', '.jpeg':'image/jpeg', '.webp':'image/webp', '.svg':'image/svg+xml', '.hdr':'application/octet-stream' };
export function createStaticServer({ directory, fallbackDirectory, onRequest = () => {} }) {
  const roots = [directory, fallbackDirectory].filter(Boolean).map(p => path.resolve(p));
  const hashes = new Map();
  for (const root of roots) {
    try { for (const entry of JSON.parse(readFileSync(path.join(root,'release-manifest.json'),'utf8')).files) hashes.set(path.join(root,entry.file),entry); } catch {}
  }
  return http.createServer(async (req, res) => {
    try {
      if (!['GET', 'HEAD'].includes(req.method)) { res.writeHead(405); res.end(); return; }
      const url = new URL(req.url, 'http://localhost');
      const relative = decodeURIComponent(url.pathname === '/' ? '/index.html' : url.pathname);
      let file, stat;
      for (const root of roots) {
        const candidate = path.resolve(root, '.' + relative);
        if (!candidate.startsWith(root + path.sep)) continue;
        try { const s = await fs.stat(candidate); if (s.isFile()) { file = candidate; stat = s; break; } } catch {}
      }
      if (!file) { res.writeHead(404); res.end('Not found'); onRequest({url:relative,status:404}); return; }
      const type = mime[path.extname(file)] || 'application/octet-stream';
      const entry = hashes.get(file);
      const accepted = (req.headers['accept-encoding'] || '').split(',').map(s => s.trim()).filter(s => !/;\s*q=0(?:\.0*)?$/.test(s));
      let encoding;
      for (const [name, ext] of [['br', '.br'], ['gzip', '.gz']]) {
        if (!accepted.some(s => s.split(';')[0] === name)) continue;
        try { const s = await fs.stat(file + ext); if (s.isFile()) { file += ext; stat = s; encoding = name; break; } } catch {}
      }
      const immutable = /\/runtime\/[a-f0-9]{16,}\//.test(relative) || /\/assets\/[^/]+-[\w-]{8,}\./.test(relative);
      const contentHash = encoding === 'br' ? entry?.brotliSha256 : encoding === 'gzip' ? entry?.gzipSha256 : entry?.sha256;
      const etag = `"${contentHash || `${stat.size.toString(16)}-${Math.trunc(stat.mtimeMs).toString(16)}`}-${encoding || 'identity'}"`;
      res.setHeader('Content-Type', type);
      res.setHeader('Cache-Control', immutable ? 'public, max-age=31536000, immutable' : 'no-cache');
      res.setHeader('ETag', etag);
      res.setHeader('Vary', 'Accept-Encoding');
      res.setHeader('X-Content-Type-Options', 'nosniff');
      if (encoding) res.setHeader('Content-Encoding', encoding);
      if (req.headers['if-none-match'] === etag) { res.writeHead(304); res.end(); onRequest({url:relative,status:304,bytes:0}); return; }
      res.setHeader('Content-Length', stat.size);
      res.writeHead(200);
      onRequest({url:relative,status:200,bytes:stat.size,encoding});
      if (req.method === 'HEAD') res.end();
      else {
        const stream = createReadStream(file);
        res.on('close', () => stream.destroy());
        stream.on('error', () => res.destroy()).pipe(res);
      }
    } catch { if (!res.headersSent) res.writeHead(400); res.end(); }
  });
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const directory = path.resolve(process.argv[2] || 'dist-release');
  const port = Number(process.argv[3] || 8081);
  await fs.access(path.join(directory, 'index.html'));
  await fs.access(path.join(directory, 'release-manifest.json'));
  const server = createStaticServer({ directory });
  server.on('error', e => { console.error(e.message); process.exitCode = 1; });
  server.listen(port, '127.0.0.1', () => console.log(`Static release: http://127.0.0.1:${port}/ (${directory})`));
  for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.close());
}
