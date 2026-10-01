'use strict';
/**
 * AgentShield injection middleware for Node websites.
 *
 * Usage (Express / connect):
 *     const { inject } = require('agentshield-inject');
 *     app.use(inject({ mapping: './agentshield.mapping.json' }));
 *
 * It matches each request's URL path against the mapping (exported by
 * `agentshield export`) and, for matched HTML responses, embeds the hidden
 * prompt markup right after <body>. Because the injection happens server-side,
 * the prompt is present in the RAW HTML every agent/scraper receives.
 */
const fs = require('fs');

function loadMapping(src) {
  if (!src) return {};
  if (typeof src === 'string') {
    try {
      return JSON.parse(fs.readFileSync(src, 'utf8').replace(/^﻿/, ''));
    } catch (e) {
      console.error('[agentshield] could not read mapping ' + src + ': ' + e.message);
      return {};
    }
  }
  return src; // already an object
}

function normPath(p) {
  p = String(p || '/').split('?')[0].split('#')[0];
  try { p = decodeURIComponent(p); } catch (e) { /* keep raw */ }
  if (p.length > 1 && p.endsWith('/')) p = p.slice(0, -1);
  return p || '/';
}

function injectIntoHtml(html, snippet) {
  if (!snippet) return html;
  const m = html.match(/<body[^>]*>/i);
  if (!m) return snippet + '\n' + html; // no <body>: prepend as a fallback
  const idx = m.index + m[0].length;
  return html.slice(0, idx) + '\n' + snippet + '\n' + html.slice(idx);
}

function inject(options) {
  options = options || {};
  const raw = loadMapping(options.mapping);
  const byPath = {};
  for (const k of Object.keys(raw)) {
    const entry = raw[k] || {};
    byPath[normPath(k)] = entry.html != null ? entry.html : '';
  }

  return function agentshieldInject(req, res, next) {
    next = next || function () {};
    const snippet = byPath[normPath(req.url)];
    if (!snippet) return next();

    const origWrite = res.write;
    const origEnd = res.end;
    const chunks = [];
    let intercepting = true;

    const isHtml = function () {
      const ct = res.getHeader && res.getHeader('content-type');
      return !ct || String(ct).toLowerCase().indexOf('html') !== -1;
    };

    res.write = function (chunk, enc, cb) {
      if (intercepting && chunk) {
        chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk, enc || 'utf8'));
        if (typeof cb === 'function') cb();
        return true;
      }
      return origWrite.call(res, chunk, enc, cb);
    };

    res.end = function (chunk, enc, cb) {
      if (!intercepting) return origEnd.call(res, chunk, enc, cb);
      intercepting = false;
      if (chunk) chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk, enc || 'utf8'));
      res.write = origWrite;
      res.end = origEnd;
      let body = Buffer.concat(chunks).toString('utf8');
      if (isHtml() && /<body/i.test(body)) {
        body = injectIntoHtml(body, snippet);
        try { res.setHeader('Content-Length', Buffer.byteLength(body)); } catch (e) { /* headers sent */ }
      }
      return origEnd.call(res, body, 'utf8', cb);
    };

    next();
  };
}

module.exports = { inject, injectIntoHtml, loadMapping, normPath };
