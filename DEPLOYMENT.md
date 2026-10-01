# Deploying AgentShield-local on a live site

The pipeline and the injector are connected by one file, `agentshield.mapping.json`:

```
OFFLINE (any machine)                          ON THE LIVE SERVER
+-------------------------------+              +------------------------------+
| agentshield (Python)          | mapping.json | agentshield-inject (Node)    |
|  add -> extract -> configure  | -----------> |  middleware or proxy service |
|  -> generate -> export        |              |  injects into HTML responses |
+-------------------------------+              +------------------------------+
```

Only the injector and `mapping.json` go on the production server. The pipeline runs offline
and uses Ollama only to write the generated prompts.

> Deploy only to a site you own or control. The injector modifies responses at serve time;
> it does not edit the origin's stored content or database.

## Step 1: produce the mapping (offline)

```bash
agentshield init                           # then set source.root to your site in the config
agentshield add /path/to/your/site         # read local products/articles
agentshield extract                        # fill structured content
agentshield configure --auto               # or interactive, or --set <url> <category> per page
agentshield generate                       # Ollama writes the generated prompts
agentshield export                         # writes agentshield.mapping.json
```

Copy `agentshield.mapping.json` to the server. For a local end-to-end walkthrough, see the
two demos in [README.md](README.md).

## Step 2: inject on the live server (choose one)

**A. Express or connect app.** Add one line before your routes:

```js
const { inject } = require('agentshield-inject');
app.use(inject({ mapping: './agentshield.mapping.json' }));
```

**B. Any framework: a standalone proxy** in the serving path. A common topology places it
behind an existing TLS edge:

```
internet -> nginx/Caddy/LB (TLS) -> agentshield-proxy :8080 -> your app :3000
```

```bash
agentshield-proxy --target http://127.0.0.1:3000 --mapping ./agentshield.mapping.json --port 8080
```

Add `--tls-cert` and `--tls-key` to terminate TLS at the proxy instead. Run it as a service
(systemd or pm2); the mapping hot-reloads when the file changes.

**C. nginx already in front.** Use `sub_filter` with the per-page snippet (see
[injector/README.md](injector/README.md)).

> **Path matching.** The mapping is keyed by URL path. The adapter's `pathTemplate` (or the
> page `url`) must match the exact path the site serves each page at, or the injector finds
> no match. Run `agentshield verify <site-url>` to check.

## Notes

- No extraction model is needed. Content is read locally; Ollama is used only for the
  generated categories (`additional`, `hidden_promotion`, `disinformation`). The `defensive`
  and `abusive` categories are constants.
- Middleware injects into all traffic through the app. The proxy injects only into traffic
  routed through it, so make it the serving path for a site-wide effect.
- Injector dependencies: none (Node 16+). Pipeline dependencies: Python 3.9+, pydantic,
  beautifulsoup4, PyYAML; Ollama for generation.
