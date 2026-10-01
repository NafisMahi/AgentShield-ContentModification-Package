# AgentShield-local

A research tool for studying indirect prompt injection on websites the operator owns. It
reads a site's products and articles from the project (files or a database), uses a local
model to write a hidden prompt for each page, and injects that prompt into the served HTML:
invisible to human visitors, but present in the raw HTML an AI agent reads. The origin's
stored content is never modified; injection happens at serve time and is reversible.

Two parts:

- **`agentshield` (Python):** an offline pipeline that reads local content, assigns a category
  to each page, generates the hidden prompts with a local model, and exports a mapping file.
- **`agentshield-inject` (Node):** an injector that runs on the server as Express middleware or
  a reverse proxy.

> Use only on sites you control. The injector alters HTTP responses at serve time; it does not
> change the origin's stored content.

## Requirements

- Python 3.9+ and Node.js 16+
- [Ollama](https://ollama.com/download) running with the `llama3.2:3b` model pulled (used only
  for prompt generation; about 2 GB, needs a few GB of RAM).

Commands below use **Windows PowerShell**. On Linux/macOS, activate the environment with
`source .venv/bin/activate` and use `/` in paths.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
ollama pull llama3.2:3b
```

Run `agentshield` with the virtual environment active (`agentshield --help` to confirm).

## Test 1: markdown demo

A store of 5 products and 5 articles, rendered from the same markdown files the pipeline reads.

Install the demo server's dependency once:

```powershell
cd demo-site; npm install; cd ..
```

1. **Pipeline** (from `demo-site`):
   ```powershell
   cd demo-site
   agentshield init
   agentshield add
   agentshield extract
   agentshield configure --auto
   agentshield generate            # calls Ollama, about 1-2 minutes
   agentshield export
   cd ..
   ```
2. **Site** (new terminal): `cd demo-site; node server.js` serves `http://127.0.0.1:8100`.
3. **Injector** (new terminal):
   ```powershell
   node injector\agentshield-proxy.js --target http://127.0.0.1:8100 --mapping demo-site\agentshield.mapping.json --port 8080
   ```
4. **Verify** (from `demo-site`):
   ```powershell
   cd demo-site
   agentshield verify http://127.0.0.1:8100 --proxy http://127.0.0.1:8080
   ```
   Expected:
   ```
   Routes: 10 ok, 0 mismatched.  Injection: 10 present, 0 missing.
   All checks passed.
   ```

Compare the injected page to the origin (the hidden span is present only through the proxy):

```powershell
curl http://127.0.0.1:8080/product/raw-wildflower-honey     # injected
curl http://127.0.0.1:8100/product/raw-wildflower-honey     # origin, unmodified
```

## Test 2: database (SQLite) demo

A store of 3 products and 2 articles in a SQLite database, served by a Python script (standard
library only). Same four steps as Test 1.

1. **Build the database and run the pipeline** (from `demo-db-site`):
   ```powershell
   cd demo-db-site
   python build_db.py
   copy config.example.json agentshield.config.json
   agentshield add
   agentshield extract
   agentshield configure --auto
   agentshield generate
   agentshield export
   cd ..
   ```
2. **Site** (new terminal): `cd demo-db-site; python server.py` serves `http://127.0.0.1:8200`.
3. **Injector** (new terminal):
   ```powershell
   node injector\agentshield-proxy.js --target http://127.0.0.1:8200 --mapping demo-db-site\agentshield.mapping.json --port 8080
   ```
4. **Verify** (from `demo-db-site`):
   ```powershell
   cd demo-db-site
   agentshield verify http://127.0.0.1:8200 --proxy http://127.0.0.1:8080
   ```
   Expected: `Routes: 5 ok, 0 mismatched.  Injection: 5 present, 0 missing.  All checks passed.`

## Test your own markdown site

The same flow, pointed at your content.

1. **Create a working folder and config:**
   ```powershell
   mkdir myrun; cd myrun
   agentshield init
   ```
2. **Edit the `source` block** of `myrun\agentshield.config.json`. Set `root` to your site's
   folder, and for each collection set `dir` (where the `.md` files are, relative to `root`)
   and `pathTemplate` (the URL your site serves them at; `{slug}` is the filename without
   `.md`, so `honey.md` becomes `/product/honey`):
   ```json
   "source": {
     "type": "markdown",
     "root": "C:/path/to/your/site",
     "collections": [
       { "type": "product", "dir": "content/products", "pathTemplate": "/product/{slug}" },
       { "type": "article", "dir": "content/articles", "pathTemplate": "/article/{slug}" }
     ]
   }
   ```
3. **Run the pipeline** (from `myrun`):
   ```powershell
   agentshield add          # prints how many pages it found (0 means root/dir is wrong)
   agentshield extract
   agentshield configure --auto
   agentshield generate
   agentshield export
   ```
4. **Start your site** the way you normally do (for example `npm run dev`), and note its
   address, for example `http://localhost:3000`.
5. **Start the injector** (new terminal, from `myrun`):
   ```powershell
   node C:\path\to\agentshield-local\injector\agentshield-proxy.js --target http://127.0.0.1:3000 --mapping agentshield.mapping.json --port 8080
   ```
6. **Verify:**
   ```powershell
   agentshield verify http://127.0.0.1:3000 --proxy http://127.0.0.1:8080
   ```
   If a route shows `404`, its `pathTemplate` does not match the real URL. Fix `pathTemplate`
   (or add a `slug:` line to that file's frontmatter), then rerun `agentshield add` and
   `agentshield export`.

For a database or other content source, write a small adapter: see
[docs/adapters.md](docs/adapters.md). For production deployment, see [DEPLOYMENT.md](DEPLOYMENT.md).

## Commands

| Command | Description |
|---|---|
| `agentshield init` | Write `agentshield.config.json`. |
| `agentshield add [dir]` | Read the local product/article pages into the manifest. |
| `agentshield extract [dir]` | Fill each page's content from the source. |
| `agentshield configure` | Assign a category per page (`--auto`, `--all <cat>`, `--set <url> <cat>`, or interactive). |
| `agentshield generate` | Generate the hidden prompts (Ollama for three categories, constants for two). |
| `agentshield export` | Write `agentshield.mapping.json` for the injector. |
| `agentshield verify <site-url> [--proxy <url>]` | Check every route is served, and that injection lands. |
| `agentshield inject` | (Optional) Write injected copies of local static HTML. |

The five categories are `defensive` and `abusive` (fixed constant texts) and `additional`,
`hidden_promotion`, and `disinformation` (generated from page content).

## How it works

`add` and `extract` read the site's content into a manifest; `configure` assigns a category
per page; `generate` writes the hidden prompt for each; `export` writes
`agentshield.mapping.json`, keyed by URL path, with the hidden HTML pre-rendered (a zero-size
CSS span and a low-opacity canvas element). The injector matches requests by path and inserts
the hidden HTML into the response. See [ARCHITECTURE.md](ARCHITECTURE.md).

## Troubleshooting

- **`agentshield: command not found`**: activate the virtual environment and run `pip install -e .`.
- **`generate` fails or hangs**: Ollama is not running or the model is not pulled. Start Ollama
  and run `ollama pull llama3.2:3b`; confirm with `curl http://localhost:11434/api/tags`.
- **`verify` shows a route `UNREACHABLE`**: the site is not running, or the wrong URL was given.
- **`verify` shows a route `404`**: the adapter's path does not match what the site serves;
  adjust `pathTemplate` (or the page `url`).
- **`verify` shows `inject MISSING`**: the proxy is not running or points at the wrong mapping
  or target.
- **`address already in use`**: another process holds the port; stop it or use a different `--port`.

## Repository layout

```
agentshield/          Python pipeline (add, extract, configure, generate, export, verify, inject)
  sources/            content-source adapters: base.py, markdown.py, sqlite_shop.py
injector/             Node injector: middleware (index.js) and reverse proxy (proxy.js)
demo-site/            markdown demo (GreenLeaf Organics), served by Express
demo-db-site/         SQLite demo (Tinderbox Coffee), served by a Python server
docs/adapters.md      how to write a source adapter for another site
ARCHITECTURE.md       component overview
DEPLOYMENT.md         production deployment
pyproject.toml        Python package definition
```
