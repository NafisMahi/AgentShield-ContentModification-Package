'use strict';
// Render the whole demo site to static HTML under dist/ (from the local markdown).
// Useful for `agentshield inject` (point injection.htmlDir at demo-site/dist).
const fs = require('fs');
const path = require('path');
const site = require('./render.js');

const OUT = path.join(__dirname, 'dist');
const ORIGIN = process.env.ORIGIN || 'http://localhost:8100';

function write(rel, html) {
  const file = path.join(OUT, rel);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, html, 'utf8');
  console.log('  wrote ' + rel);
}

fs.rmSync(OUT, { recursive: true, force: true });
write('index.html', site.homePage());
write('shop/index.html', site.shopPage());
write('blog/index.html', site.blogPage());
for (const slug of Object.keys(site.products())) write('product/' + slug + '.html', site.productPage(slug));
for (const slug of Object.keys(site.articles())) write('article/' + slug + '.html', site.articlePage(slug));
write('sitemap.xml', site.sitemapXml(ORIGIN));
write('robots.txt', site.robotsTxt(ORIGIN));
console.log('Static build complete -> ' + OUT);
