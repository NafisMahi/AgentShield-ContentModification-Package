'use strict';
/**
 * GreenLeaf Organics demo: content and rendering driven by the local markdown files.
 *
 * The .md files in content/products and content/articles are what both the demo site
 * and the pipeline read. Uses a small frontmatter parser and string templates; no
 * build step.
 */
const fs = require('fs');
const path = require('path');

const CONTENT_DIR = path.join(__dirname, 'content');

// --- tiny YAML-frontmatter parser (scalars, quoted strings, booleans) ---------
function parseFrontmatter(text) {
  text = text.replace(/^﻿/, '');
  const m = /^---\s*\r?\n([\s\S]*?)\r?\n---\s*\r?\n?/.exec(text);
  if (!m) return { data: {}, body: text.trim() };
  const data = {};
  for (const line of m[1].split(/\r?\n/)) {
    if (!line.trim() || line.trim().startsWith('#')) continue;
    const idx = line.indexOf(':');
    if (idx === -1) continue;
    const key = line.slice(0, idx).trim();
    let val = line.slice(idx + 1).trim();
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1);
    } else if (val === 'true' || val === 'false') {
      data[key] = val === 'true';
      continue;
    }
    data[key] = val;
  }
  return { data, body: text.slice(m[0].length).trim() };
}

function loadCollection(name) {
  const dir = path.join(CONTENT_DIR, name);
  const out = {};
  if (!fs.existsSync(dir)) return out;
  for (const file of fs.readdirSync(dir).sort()) {
    if (!/\.(md|markdown|mdx)$/i.test(file)) continue;
    const slug = file.replace(/\.(md|markdown|mdx)$/i, '');
    const { data, body } = parseFrontmatter(fs.readFileSync(path.join(dir, file), 'utf8'));
    out[slug] = Object.assign({}, data, { slug, body });
  }
  return out;
}

// Re-read on every request so edits show up live (small demo; fine to reload).
function products() { return loadCollection('products'); }
function articles() { return loadCollection('articles'); }

function esc(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function paragraphs(body) {
  return String(body || '').split(/\n\s*\n/).map((p) => '<p>' + esc(p.trim()) + '</p>').join('\n');
}

const CSS = `
:root{--bg:#f7f6f1;--ink:#23281f;--green:#3f6f42;--green2:#5b8c5a;--muted:#6b7268;--card:#fff;--line:#e4e2d8}
*{box-sizing:border-box}body{margin:0;font:16px/1.6 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg)}
a{color:var(--green);text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:1000px;margin:0 auto;padding:0 20px}
header.site{background:var(--green);color:#fff}
header.site .wrap{display:flex;align-items:center;justify-content:space-between;padding:14px 20px}
header.site a{color:#fff}
.brand{font-weight:700;font-size:20px;letter-spacing:.3px}
nav a{margin-left:18px;font-weight:500}
.hero{background:linear-gradient(120deg,#eef3e9,#f7f6f1);padding:48px 0;border-bottom:1px solid var(--line)}
.hero h1{margin:0 0 8px;font-size:32px}.hero p{margin:0;color:var(--muted);max-width:640px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:20px;margin:28px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;transition:box-shadow .15s}
.card:hover{box-shadow:0 6px 20px rgba(0,0,0,.06)}
.thumb{height:120px;background:linear-gradient(135deg,#dce8d5,#c7dbc0)}
.card .body{padding:14px}.card h3{margin:0 0 6px;font-size:16px}.card .price{font-weight:700;color:var(--green)}
.card .muted{color:var(--muted);font-size:14px}
main.wrap{padding:26px 20px 60px}
.product{display:grid;grid-template-columns:1fr 1fr;gap:32px;margin-top:20px}
.product .media{height:280px;border-radius:14px;background:linear-gradient(135deg,#dce8d5,#bcd3b3)}
.product h1{margin:0 0 6px}.price-row{display:flex;align-items:center;gap:12px;margin:10px 0}
.price-row .price{font-size:24px;font-weight:800;color:var(--green)}.was{color:var(--muted);text-decoration:line-through}
.badge{display:inline-block;background:#eaf3e6;color:var(--green);border-radius:999px;padding:2px 10px;font-size:13px}
.buy{margin-top:16px;background:var(--green);color:#fff;border:0;border-radius:10px;padding:12px 20px;font-size:16px;cursor:pointer}
.post{max-width:720px;margin:0 auto}.post h1{font-size:30px;margin-bottom:6px}.post .meta{color:var(--muted);margin-bottom:20px}
.post p{margin:0 0 16px}
.postlist{list-style:none;padding:0}.postlist li{border-bottom:1px solid var(--line);padding:16px 0}
.postlist h3{margin:0 0 4px}.postlist .muted{color:var(--muted);font-size:14px}
footer.site{border-top:1px solid var(--line);color:var(--muted);padding:28px 0;margin-top:30px;font-size:14px}
`;

function layout(title, main) {
  return '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n' +
    '<meta name="viewport" content="width=device-width, initial-scale=1">\n' +
    '<title>' + esc(title) + ' — GreenLeaf Organics</title>\n<style>' + CSS + '</style>\n</head>\n<body>\n' +
    '<header class="site"><div class="wrap"><a class="brand" href="/">🌿 GreenLeaf Organics</a>' +
    '<nav><a href="/shop">Shop</a><a href="/blog">Journal</a><a href="/">Home</a></nav></div></header>\n' +
    '<main class="wrap">\n' + main + '\n</main>\n' +
    '<footer class="site"><div class="wrap">© 2026 GreenLeaf Organics — wholesome food, honestly made.</div></footer>\n' +
    '</body>\n</html>\n';
}

function card(href, title, sub, price) {
  return '<a class="card" href="' + href + '"><div class="thumb"></div><div class="body">' +
    '<h3>' + esc(title) + '</h3><div class="muted">' + esc(sub) + '</div>' +
    (price ? '<div class="price">' + esc(price) + '</div>' : '') + '</div></a>';
}

function homePage() {
  const P = products();
  const A = articles();
  const featured = Object.keys(P).slice(0, 3)
    .map((s) => card('/product/' + s, P[s].title, P[s].category, P[s].price)).join('');
  const posts = Object.keys(A).slice(0, 3)
    .map((s) => card('/article/' + s, A[s].title, A[s].date)).join('');
  return layout('Home',
    '<section class="hero"><div><h1>Wholesome food, honestly made.</h1>' +
    '<p>Small-batch pantry staples and a journal on eating well — unfiltered, cold-pressed, and organic.</p></div></section>' +
    '<h2>Featured products</h2><div class="grid">' + featured + '</div>' +
    '<h2>From the Journal</h2><div class="grid">' + posts + '</div>');
}

function shopPage() {
  const P = products();
  const cards = Object.keys(P).map((s) => card('/product/' + s, P[s].title, P[s].short, P[s].price)).join('');
  return layout('Shop', '<h1>Shop</h1><div class="grid">' + cards + '</div>');
}

function blogPage() {
  const A = articles();
  const items = Object.keys(A).map((s) => '<li><h3><a href="/article/' + s + '">' + esc(A[s].title) +
    '</a></h3><div class="muted">' + esc(A[s].date) + ' · ' + esc(A[s].author) + '</div><p>' +
    esc(A[s].excerpt) + '</p></li>').join('');
  return layout('Journal', '<h1>The Journal</h1><ul class="postlist">' + items + '</ul>');
}

function productPage(slug) {
  const p = products()[slug];
  if (!p) return null;
  const priceRow = '<div class="price-row"><span class="price">' + esc(p.price) + '</span>' +
    (p.was ? '<span class="was">' + esc(p.was) + '</span><span class="badge">Sale</span>' : '') + '</div>';
  const inStock = p.availability === true || p.availability === 'true' || p.availability === 'In stock';
  return layout(p.title,
    '<article class="product"><div class="media"></div><div class="info">' +
    '<div class="badge">' + esc(p.category) + '</div>' +
    '<h1 class="product-title">' + esc(p.title) + '</h1>' + priceRow +
    '<p class="stock muted">' + (inStock ? 'In stock · Free shipping over $35' : 'Out of stock') + '</p>' +
    '<div class="product-description">' + paragraphs(p.body) + '</div>' +
    '<button class="buy">Add to cart</button></div></article>');
}

function articlePage(slug) {
  const a = articles()[slug];
  if (!a) return null;
  return layout(a.title,
    '<article class="post"><h1 class="post-title">' + esc(a.title) + '</h1>' +
    '<div class="meta">' + esc(a.date) + ' · by ' + esc(a.author) + '</div>' +
    '<div class="post-content">' + paragraphs(a.body) + '</div></article>');
}

function sitemapXml(origin) {
  const urls = []
    .concat(Object.keys(products()).map((s) => origin + '/product/' + s))
    .concat(Object.keys(articles()).map((s) => origin + '/article/' + s));
  return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    urls.map((u) => '  <url><loc>' + u + '</loc></url>').join('\n') + '\n</urlset>\n';
}

function robotsTxt(origin) {
  return 'User-agent: *\nAllow: /\nSitemap: ' + origin + '/sitemap.xml\n';
}

module.exports = {
  products, articles, CSS,
  homePage, shopPage, blogPage, productPage, articlePage, sitemapXml, robotsTxt,
};
