# GreenLeaf demo site (markdown)

A small content site (5 products, 5 articles) used to test AgentShield-local end to end. The
markdown files in [`content/`](content/) are read by both this demo server and the pipeline.

```
content/
  products/*.md     frontmatter (title, price, category, availability) + body
  articles/*.md     frontmatter (title, author, date, excerpt) + body
render.js           frontmatter parser and page templates
server.js           Express server
build-static.js     render everything to static HTML in dist/ (optional)
```

## Run

```powershell
npm install
node server.js          # serves http://127.0.0.1:8100
```

Pages: `/`, `/shop`, `/blog`, `/product/<slug>`, `/article/<slug>`.

For the full test (pipeline, injector, and verify), see the [repository README](../README.md).
