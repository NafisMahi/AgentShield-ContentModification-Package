# agentshield-inject

Inserts the hidden prompt markup (from the `mapping.json` produced by `agentshield export`)
into a site's HTML responses, matched by URL path, at serve time. The origin's stored content
and database are not modified. No dependencies; Node 16+.

## Install on the server

This package is not on the public npm registry, so install it from the repository:

```bash
git clone <repo-url>
npm install ./agentshield-local/injector
# for the proxy command, install globally:
npm install -g ./agentshield-local/injector
```

Copy `agentshield.mapping.json` to the server as well.

## Which option to use

| Your site | Use |
|---|---|
| An Express app you can edit | Middleware (one line) |
| Anything else, or you do not want to edit the app | Proxy (in front of it) |
| Already fronted by nginx and you prefer no extra process | nginx `sub_filter` |

## Option A: Express middleware

In your server file, before your routes:

```js
const { inject } = require('agentshield-inject');   // or require('./injector')
app.use(inject({ mapping: './agentshield.mapping.json' }));
```

Restart the app. Every page in the mapping now serves the hidden prompt.

## Option B: reverse proxy (any framework)

The proxy sits between visitors and the app. Steps for the common case where nginx already
fronts the app (app on port 3000):

1. Put the files on the server and install the command:

```bash
scp agentshield.mapping.json you@server:/home/you/
ssh you@server
npm install -g ./agentshield-local/injector
```

2. Run the proxy as a service (listens on 8080, forwards to the app on 3000):

```bash
pm2 start agentshield-proxy --name injector -- \
  --target http://127.0.0.1:3000 \
  --mapping /home/you/agentshield.mapping.json \
  --port 8080
pm2 save
```

3. Point nginx at the proxy instead of the app. In the site config, under `location /`,
   change the upstream address:

```nginx
location / {
    proxy_pass http://127.0.0.1:8080;    # was http://127.0.0.1:3000
}
```

4. Reload nginx:

```bash
sudo nginx -t && sudo nginx -s reload
```

Traffic now flows `visitor -> nginx (HTTPS) -> injector :8080 -> app :3000`, and each mapped
page gets the hidden prompt. The app is unchanged.

If the app is directly public (no nginx), move it to an internal port and run the proxy on
the public port with a certificate:

```bash
agentshield-proxy --target http://127.0.0.1:3000 --mapping ./agentshield.mapping.json \
  --port 443 --tls-cert /etc/ssl/site.crt --tls-key /etc/ssl/site.key
```

### Proxy options

`--target <url>` (the app), `--mapping <file>`, `--port <n>` (default 8080),
`--tls-cert`/`--tls-key <file>` (serve HTTPS), `--timeout <ms>`, `--log`. Options can also be
placed in a JSON file passed with `--config injector.json`:

```json
{ "target": "http://127.0.0.1:3000", "mapping": "./agentshield.mapping.json", "port": 8080 }
```

Non-HTML and non-mapped responses pass straight through; only mapped 200 HTML responses are
rewritten. The mapping file reloads when it changes, with no restart.

## Option C: nginx sub_filter

nginx can insert the markup itself with `sub_filter`. This is practical only for a few pages,
since each page's snippet goes into the config:

```nginx
location = /article/cold-pressed-vs-refined-oils {
    proxy_pass http://127.0.0.1:3000;
    sub_filter '<body>' '<body><!-- the page mapping .html value -->';
    sub_filter_once on;
}
```

The proxy (Option B) handles all pages automatically, so prefer it unless you specifically
want no extra process.

## API

- `inject({ mapping })`: Express/connect middleware.
- `injectIntoHtml(html, snippet)`: pure function, for custom framework adapters.
- `createServer({ target, mapping, tls, timeoutMs })` (from `proxy.js`): an http/https proxy
  server.
