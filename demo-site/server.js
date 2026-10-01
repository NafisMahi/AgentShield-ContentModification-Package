'use strict';
// GreenLeaf demo served by Express, rendered from the local markdown in content/.
// Optional in-app injection: set AGENTSHIELD_MAPPING to a mapping.json path.
const express = require('express');
const site = require('./render.js');
const app = express();
const PORT = process.env.PORT || 8100;
const ORIGIN = process.env.ORIGIN || ('http://localhost:' + PORT);

if (process.env.AGENTSHIELD_MAPPING) {
  const { inject } = require('../injector');
  app.use(inject({ mapping: process.env.AGENTSHIELD_MAPPING }));
  console.log('[express] injection middleware ON');
}

app.get('/', (req, res) => res.type('html').send(site.homePage()));
app.get('/shop', (req, res) => res.type('html').send(site.shopPage()));
app.get('/blog', (req, res) => res.type('html').send(site.blogPage()));
app.get('/product/:slug', (req, res) => {
  const h = site.productPage(req.params.slug);
  return h ? res.type('html').send(h) : res.status(404).send('Not found');
});
app.get('/article/:slug', (req, res) => {
  const h = site.articlePage(req.params.slug);
  return h ? res.type('html').send(h) : res.status(404).send('Not found');
});
app.get('/sitemap.xml', (req, res) => res.type('application/xml').send(site.sitemapXml(ORIGIN)));
app.get('/robots.txt', (req, res) => res.type('text/plain').send(site.robotsTxt(ORIGIN)));

app.listen(PORT, () => console.log('[express] GreenLeaf (markdown-driven) on ' + ORIGIN));
