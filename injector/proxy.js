'use strict';
/**
 * Reverse-proxy injector. Sits in front of any website (any framework or
 * language) and injects the hidden prompt markup into HTML responses by URL.
 *
 * Production topology (typical): TLS is terminated by your existing edge
 * (nginx / Caddy / cloud LB), which forwards plain HTTP to this injector, which
 * forwards to your app. The injector can also terminate TLS itself if given a
 * cert (see the CLI --tls-cert/--tls-key).
 *
 *   edge(TLS) -> [agentshield injector] -> origin app
 *
 * Design:
 *  - Non-injected responses stream straight through (no buffering).
 *  - Only 2xx HTML responses whose path is mapped are buffered + rewritten.
 *  - Upstream keep-alive, timeouts, and error handling included.
 *  - The mapping file is hot-reloaded on change (no restart needed).
 */
const http = require('http');
const https = require('https');
const fs = require('fs');
const { URL } = require('url');
const { injectIntoHtml, loadMapping, normPath } = require('./index.js');

function buildIndex(raw) {
  const byPath = {};
  for (const k of Object.keys(raw || {})) byPath[normPath(k)] = (raw[k] || {}).html || '';
  return byPath;
}

/**
 * Returns an (req, res) handler. Options:
 *   target (url, required), mapping (path or object), timeoutMs, log
 */
function createHandler(options) {
  options = options || {};
  const target = new URL(options.target);
  const isHttps = target.protocol === 'https:';
  const client = isHttps ? https : http;
  const agent = new client.Agent({ keepAlive: true, maxSockets: 128 });
  const timeoutMs = options.timeoutMs || 30000;
  const log = options.log || function () {};

  let byPath = buildIndex(loadMapping(options.mapping));
  // Hot-reload the mapping file on change (best-effort).
  if (typeof options.mapping === 'string') {
    try {
      fs.watch(options.mapping, { persistent: false }, function () {
        try { byPath = buildIndex(loadMapping(options.mapping)); log('mapping reloaded'); }
        catch (e) { log('mapping reload failed: ' + e.message); }
      });
    } catch (e) { /* watch unsupported; ignore */ }
  }

  return function handler(req, res) {
    const snippet = byPath[normPath(req.url)];

    const headers = Object.assign({}, req.headers);
    headers.host = target.host;
    headers['accept-encoding'] = 'identity'; // uncompressed so we can inject
    delete headers['connection'];

    const upstream = client.request({
      protocol: target.protocol,
      hostname: target.hostname,
      port: target.port || (isHttps ? 443 : 80),
      method: req.method,
      path: req.url,
      headers: headers,
      agent: agent,
      timeout: timeoutMs,
    }, function (pres) {
      const status = pres.statusCode || 502;
      const ctype = String(pres.headers['content-type'] || '').toLowerCase();
      const injectable = !!snippet && status >= 200 && status < 300 && ctype.indexOf('html') !== -1;

      if (!injectable) {
        res.writeHead(status, pres.headers);
        pres.pipe(res);            // stream straight through
        return;
      }

      const chunks = [];
      let total = 0;
      pres.on('data', function (c) { chunks.push(c); total += c.length; });
      pres.on('end', function () {
        let body = Buffer.concat(chunks, total).toString('utf8');
        body = injectIntoHtml(body, snippet);
        const out = Object.assign({}, pres.headers);
        delete out['content-length'];
        delete out['transfer-encoding'];
        out['content-length'] = Buffer.byteLength(body);
        res.writeHead(status, out);
        res.end(body);
      });
      pres.on('error', function () { try { res.destroy(); } catch (e) {} });
    });

    upstream.on('timeout', function () { upstream.destroy(new Error('upstream timeout')); });
    upstream.on('error', function (e) {
      if (!res.headersSent) { res.writeHead(502, { 'content-type': 'text/plain' }); res.end('AgentShield proxy: upstream error (' + e.message + ')'); }
      else { try { res.destroy(); } catch (x) {} }
    });
    req.on('error', function () { try { upstream.destroy(); } catch (e) {} });
    req.pipe(upstream);
  };
}

/** Create an http or https server around the handler. tls = { cert, key } (PEM strings). */
function createServer(options) {
  const handler = createHandler(options);
  if (options.tls && options.tls.cert && options.tls.key) {
    return https.createServer({ cert: options.tls.cert, key: options.tls.key }, handler);
  }
  return http.createServer(handler);
}

module.exports = { createHandler, createServer };
