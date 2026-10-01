# AgentShield-local: Architecture

An overview of the components, how a hidden prompt reaches a served page, and where each
piece lives.

## 1. The basic idea

A web server sends HTML text in response to a request. A browser renders that text into a
visual page; an AI agent or scraper reads the text directly. So a prompt placed in the HTML
that is invisible to humans (a zero-size CSS span and low-opacity canvas text) is still read
by an agent that ingests the page.

## 2. Two programs and one handoff file

```
+------------------------------+   writes    +------------------+   reads    +----------------------------+
|  agentshield  (Python)       | ----------> |  mapping.json    | ---------> |  agentshield-inject (Node) |
|  content pipeline            |             |  path -> hidden  |            |  the injector              |
|  reads local content,        |             |       html       |            |  serves it on the site     |
|  runs offline                |             +------------------+            |  runs on the server        |
+------------------------------+                                            +----------------------------+
```

The pipeline reads the site's content and uses a local model (Ollama) to write prompts. The
injector runs inside or in front of the web server. `mapping.json` is the only file that
passes between them, so they can run on different machines.

## 3. The manifest

One JSON file, `agentshield.manifest.json`, accumulates state as each command runs:

```
add       -> { url, title, type }
extract   -> + { content{ title, description, price, ... } }
configure -> + { category }
generate  -> + { injection_prompt }
export    -> writes mapping.json
```

`add` enumerates the pages and `extract` fills their structured content; both are direct
reads from the configured source adapter.

## 4. The content-source adapter

`add` and `extract` call one object, a *source*, with a single method `load()` that returns
the site's pages as dicts (url, type, structured content). The source is chosen by
`source.type` in the config. Two adapters ship with the tool:

- `markdown`: reads `.md` files with YAML frontmatter.
- `sqlite_shop`: reads `products` and `articles` tables from a SQLite database.

For another storage system, add a class with a `load()` method and register it. See
[docs/adapters.md](docs/adapters.md). The pipeline is generic; only the adapter knows the
site's storage.

## 5. Injection

The injector reads `mapping.json` and inserts the hidden markup into HTTP responses, matching
each request by URL path. There are two ways to run it:

- **Middleware:** one line added to a Node/Express app (`app.use(inject({ mapping }))`),
  which rewrites each HTML response.
- **Reverse proxy:** a standalone server placed in front of the site. It forwards requests
  to the app and injects into HTML responses on the way back. It works for any framework or
  language because it only needs HTTP.

The mapping is keyed by URL path (`/product/honey`), not the full address, so one mapping
file works on any host or port. That path comes from the adapter's `pathTemplate` (or the
page `url`) and must match how the site routes each page.

## 6. Files

### `agentshield/` (Python pipeline)

| File | Role |
|---|---|
| `cli.py` | The commands: init, add, extract, configure, generate, export, verify, inject. |
| `config.py` | Config template and loader. |
| `manifest.py` | Reads and writes the manifest. |
| `sources/base.py` | The adapter contract, the `SOURCES` registry, and `normalize_content`. |
| `sources/markdown.py` | Markdown + YAML frontmatter adapter. |
| `sources/sqlite_shop.py` | SQLite database adapter. |
| `extract.py` | Reads the local source; used by add and extract. |
| `schemas.py` | The `PageContent` field shape adapters target. |
| `generate.py` | Per-category prompt text (constants and Ollama). |
| `inject.py` | Builds the hidden markup; used by export and inject. |

### `injector/` (Node injector, no dependencies)

| File | Role |
|---|---|
| `index.js` | The Express/connect middleware and core `injectIntoHtml`. |
| `proxy.js` | The reverse-proxy engine. |
| `agentshield-proxy.js` | The proxy command line. |

### Demos

- `demo-site/`: markdown store (GreenLeaf Organics), served by Express (`server.js`),
  rendered from the same `content/*.md` files the pipeline reads.
- `demo-db-site/`: SQLite store (Tinderbox Coffee), served by a Python server (`server.py`),
  reading the same database the pipeline reads.

## 7. End-to-end flow

1. `agentshield init` writes the config.
2. `agentshield add` enumerates local pages.
3. `agentshield extract` fills each page's content.
4. `agentshield configure` assigns a category per page.
5. `agentshield generate` writes each page's hidden prompt.
6. `agentshield export` writes `mapping.json`.
7. `agentshield verify` confirms routes and injection.
8. On the server, the injector (middleware or proxy) inserts the prompts into responses.

Steps 1 through 7 run offline; step 8 is the deployed injector. See
[DEPLOYMENT.md](DEPLOYMENT.md) for production steps.
