#!/usr/bin/env node
'use strict';
/**
 * CLI for the reverse-proxy injector.
 *
 * Flags (or a --config <file> JSON with the same keys):
 *   --target <url>        origin app to forward to        (required)
 *   --mapping <file>      agentshield.mapping.json         (required)
 *   --port <n>            listen port                      (default 8080)
 *   --tls-cert <file>     PEM cert -> terminate TLS here   (optional)
 *   --tls-key <file>      PEM key                          (optional)
 *   --timeout <ms>        upstream timeout                 (default 30000)
 *   --log                 log each request
 *
 * Example (behind an existing TLS edge, plain HTTP):
 *   agentshield-proxy --target http://127.0.0.1:3000 --mapping ./agentshield.mapping.json --port 8080
 */
const fs = require('fs');
const { createServer } = require('./proxy.js');

function flag(name, def) {
  const i = process.argv.indexOf('--' + name);
  if (i === -1) return def;
  const next = process.argv[i + 1];
  return (next && !next.startsWith('--')) ? next : true;
}

let cfg = {};
const configFile = flag('config');
if (configFile) {
  try { cfg = JSON.parse(fs.readFileSync(configFile, 'utf8').replace(/^﻿/, '')); }
  catch (e) { console.error('Could not read --config ' + configFile + ': ' + e.message); process.exit(1); }
}

const target = flag('target', cfg.target);
const mapping = flag('mapping', cfg.mapping);
const port = parseInt(flag('port', cfg.port || 8080), 10);
const timeoutMs = parseInt(flag('timeout', cfg.timeoutMs || 30000), 10);
const doLog = flag('log', cfg.log) ? true : false;

const certFile = flag('tls-cert', cfg.tls && cfg.tls.certFile);
const keyFile = flag('tls-key', cfg.tls && cfg.tls.keyFile);

if (!target || !mapping) {
  console.error('Usage: agentshield-proxy --target <url> --mapping <mapping.json> [--port 8080] [--tls-cert cert.pem --tls-key key.pem]');
  process.exit(1);
}

let tls = null;
if (certFile && keyFile) {
  try { tls = { cert: fs.readFileSync(certFile), key: fs.readFileSync(keyFile) }; }
  catch (e) { console.error('Could not read TLS cert/key: ' + e.message); process.exit(1); }
}

const server = createServer({
  target: target, mapping: mapping, timeoutMs: timeoutMs, tls: tls,
  log: doLog ? (m) => console.log('[agentshield] ' + m) : undefined,
});

server.on('error', function (e) { console.error('[agentshield] server error: ' + e.message); process.exit(1); });
server.listen(port, function () {
  const scheme = tls ? 'https' : 'http';
  console.log('[agentshield] injector on ' + scheme + '://0.0.0.0:' + port + ' -> ' + target +
              ' (mapping: ' + mapping + (tls ? ', TLS on' : '') + ')');
});

function shutdown() { console.log('[agentshield] shutting down'); server.close(function () { process.exit(0); }); setTimeout(() => process.exit(0), 3000); }
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
