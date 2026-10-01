"""agentshield-local CLI: init / add / extract / configure / generate / inject / export.

Content is read directly from the website's project folder (no crawling): `add`
enumerates the local product/article pages, `extract` fills each page's structured
content from the same local source. The remaining stages are unchanged.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from . import config as config_mod
from . import manifest as manifest_mod
from .extract import index_by_url, load_local
from .generate import generate_for_page, product_labels
from .inject import inject_into_html, build_markup, CSS_CLASS

INJECTED_DIR = "injected"


def _slug(url):
    tail = urlparse(url).path.rstrip("/").split("/")[-1] or "page"
    return re.sub(r"[^A-Za-z0-9._-]", "_", tail)[:80]


def _load_cfg_with_root(path_override):
    cfg = config_mod.load_config(".")
    if path_override:
        cfg.setdefault("source", {})["root"] = path_override
    return cfg


# --------------------------------------------------------------------------
# init
# --------------------------------------------------------------------------
def cmd_init(args):
    path = Path(config_mod.CONFIG_FILE)
    if path.exists() and not args.force:
        print(f"{config_mod.CONFIG_FILE} already exists. Use --force to overwrite.", file=sys.stderr)
        sys.exit(1)
    config_mod.write_template(".")
    print(f"Wrote {config_mod.CONFIG_FILE}")
    print("Edit `source` to point at your site's local content (default: markdown files in")
    print("content/products and content/articles), then run `agentshield add [project-dir]`.")


# --------------------------------------------------------------------------
# add  (stage 1: enumerate local content pages)
# --------------------------------------------------------------------------
def cmd_add(args):
    try:
        cfg = _load_cfg_with_root(args.path)
    except Exception as e:  # noqa: BLE001
        print(str(e), file=sys.stderr)
        sys.exit(1)

    stype = (cfg.get("source") or {}).get("type")
    root = (cfg.get("source") or {}).get("root", ".")
    print(f"Reading local content via the '{stype}' source (root: {root}) ...")
    try:
        pages = load_local(cfg)
    except Exception as e:  # noqa: BLE001
        print("  FAILED: " + str(e), file=sys.stderr)
        sys.exit(1)

    if not pages:
        print("  No content pages found. Check `source` in the config (dirs, file extensions).",
              file=sys.stderr)
        sys.exit(1)

    by_type = Counter(p["type"] for p in pages)
    print(f"  Found {len(pages)} page(s): " + ", ".join(f"{t}={c}" for t, c in sorted(by_type.items())))
    for p in pages:
        print(f"    - [{p['type']:<8}] {p['title'] or '(untitled)'}  {p['url']}")

    if args.dry:
        print("\n(dry run: manifest not written)")
        return

    data = manifest_mod.load_manifest(".")
    by_url = {p["url"]: p for p in data["pages"]}
    added = 0
    for p in pages:
        entry = by_url.get(p["url"], {})
        if p["url"] not in by_url:
            added += 1
        entry.update({
            "url": p["url"],
            "title": p.get("title", ""),
            "type": p.get("type"),
            "source": "local",
            "source_path": p.get("source_path"),
        })
        by_url[p["url"]] = entry
    data["pages"] = list(by_url.values())
    manifest_mod.save_manifest(data, ".")
    print(f"\nManifest updated: {added} new, {len(data['pages'])} total "
          f"({manifest_mod.MANIFEST_FILE}). Run `agentshield extract` next.")


# --------------------------------------------------------------------------
# extract  (stage 2: fill structured content from the local source)
# --------------------------------------------------------------------------
def cmd_extract(args):
    try:
        cfg = _load_cfg_with_root(args.path)
    except Exception as e:  # noqa: BLE001
        print(str(e), file=sys.stderr)
        sys.exit(1)

    data = manifest_mod.load_manifest(".")
    all_pages = data["pages"]
    if not all_pages:
        print("Manifest has no pages. Run `agentshield add` first.", file=sys.stderr)
        sys.exit(1)

    try:
        loaded = index_by_url(load_local(cfg))
    except Exception as e:  # noqa: BLE001
        print("Failed to read local content: " + str(e), file=sys.stderr)
        sys.exit(1)

    pages = all_pages
    if args.url:
        pages = [p for p in all_pages if p["url"] == args.url]
        if not pages:
            print(f"URL not in manifest: {args.url}", file=sys.stderr)
            sys.exit(1)
    elif not args.force:
        pending = [p for p in all_pages if not (p.get("content") and (p.get("extract") or {}).get("ok"))]
        done = len(all_pages) - len(pending)
        if done:
            print(f"(incremental: {done} already extracted, {len(pending)} to do; --force to redo all)")
        pages = pending
        if not pages:
            print("Nothing to extract: all pages already have content (use --force to redo).")
            return

    counts = {"ok": 0, "other": 0, "failed": 0}
    print(f"Extracting {len(pages)} page(s) from the local source ...")
    for p in pages:
        src = loaded.get(p["url"])
        if src is None:
            p["content"] = None
            p["extract"] = {"ok": False, "error": "not found in local source (moved/renamed/removed?)"}
            counts["failed"] += 1
            print(f"  {p['url']} ... FAILED (not in local source)", file=sys.stderr)
            continue
        content = src.get("content") or {}
        p["content"] = content
        p["type"] = src.get("type") or content.get("type")
        if p["type"] == "other":
            p["extract"] = {"ok": True, "note": "classified as 'other'"}
            counts["other"] += 1
            print(f"  {p['url']} ... ok (other)")
        else:
            p["extract"] = {"ok": True}
            counts["ok"] += 1
            print(f"  {p['url']} ... ok ({p['type']})")

    print(f"\nSummary: {counts['ok']} ok, {counts['other']} other, {counts['failed']} failed.")

    if args.dry:
        print("\n(dry run: manifest not written)\n")
        for p in pages:
            print(f"[{p.get('type')}] {p['url']}")
            if isinstance(p.get("content"), dict):
                for k, v in p["content"].items():
                    if v in (None, "", [], {}):
                        continue
                    shown = str(v)
                    print(f"   {k}: {shown[:100] + '...' if len(shown) > 100 else shown}")
        return

    manifest_mod.save_manifest(data, ".")
    print(f"Manifest updated ({manifest_mod.MANIFEST_FILE}).")


def _assign_random_disinfo_label(page):
    """Product + 'disinformation' -> pick a random target label (spreads across labels); else clear."""
    if page.get("category") == "disinformation" and page.get("type") == "product":
        labels = product_labels(page.get("content") or {})
        if labels:
            page["disinfo_label"] = random.choice(list(labels.keys()))
            return
    page.pop("disinfo_label", None)


def _prompt_disinfo_label(page):
    """Interactive: ask which label a product's disinformation should falsify."""
    if not (page.get("category") == "disinformation" and page.get("type") == "product"):
        page.pop("disinfo_label", None)
        return
    labels = product_labels(page.get("content") or {})
    if not labels:
        page.pop("disinfo_label", None)
        return
    keys = list(labels.keys())
    print("    which label should the disinformation falsify?")
    for i, k in enumerate(keys, 1):
        print(f"      {i}) {k}: {labels[k]}")
    print("      r) random")
    while True:
        try:
            ans = input(f"      label [1-{len(keys)} / r]: ").strip().lower()
        except EOFError:
            ans = "r"
        if ans in ("r", ""):
            page["disinfo_label"] = random.choice(keys)
            print(f"        -> {page['disinfo_label']} (random)")
            return
        if ans.isdigit() and 1 <= int(ans) <= len(keys):
            page["disinfo_label"] = keys[int(ans) - 1]
            print(f"        -> {page['disinfo_label']}")
            return
        print("      invalid, try again")


# --------------------------------------------------------------------------
# configure  (stage 3: assign a category to each page)
# --------------------------------------------------------------------------
def cmd_configure(args):
    try:
        cfg = config_mod.load_config(".")
    except Exception as e:  # noqa: BLE001
        print(str(e), file=sys.stderr)
        sys.exit(1)
    categories = (cfg.get("injection") or {}).get("categories") or []
    data = manifest_mod.load_manifest(".")
    pages = data["pages"]
    if not pages:
        print("Manifest has no pages. Run `agentshield add` first.", file=sys.stderr)
        sys.exit(1)

    def require_valid(cat):
        if cat not in categories:
            print(f"Unknown category '{cat}'. Choices: {', '.join(categories)}", file=sys.stderr)
            sys.exit(1)

    interactive = args.interactive or (
        not (args.all or args.set or args.auto) and sys.stdin.isatty())
    if interactive:
        print("Assign a hidden-prompt category to each page (prompts are generated from this):\n")
        for i, c in enumerate(categories, 1):
            print(f"  {i}) {c}")
        print("  s) skip / keep current")
        for p in pages:
            cur = p.get("category")
            while True:
                prompt = (f"\n[{p.get('type', '?')}] {p['url']}\n"
                          f"  choose 1-{len(categories)}" + (f" (current: {cur})" if cur else "") + " [s=skip]: ")
                try:
                    ans = input(prompt).strip().lower()
                except EOFError:
                    ans = "s"
                if ans in ("s", ""):
                    break
                if ans.isdigit() and 1 <= int(ans) <= len(categories):
                    p["category"] = categories[int(ans) - 1]
                    print(f"    -> {p['category']}")
                    _prompt_disinfo_label(p)   # product+disinfo -> choose which label
                    break
                print("  invalid choice, try again")
        manifest_mod.save_manifest(data, ".")
        dist = Counter(p.get("category") for p in pages if p.get("category"))
        print("\nSaved. Distribution: " + ", ".join(f"{c}={dist.get(c, 0)}" for c in categories))
        return

    if args.all:
        require_valid(args.all)
        for p in pages:
            p["category"] = args.all
            _assign_random_disinfo_label(p)
    elif args.set:
        url, cat = args.set
        require_valid(cat)
        match = [p for p in pages if p["url"] == url]
        if not match:
            print(f"URL not in manifest: {url}", file=sys.stderr)
            sys.exit(1)
        match[0]["category"] = cat
        _assign_random_disinfo_label(match[0])
    elif args.auto:
        for i, p in enumerate(pages):
            p["category"] = categories[i % len(categories)]
            _assign_random_disinfo_label(p)
    else:
        print(f"Categories: {', '.join(categories)}\n")
        for p in pages:
            print(f"  [{p.get('category', 'unassigned'):<16}] {p['url']}")
        print("\nAssign with: configure --auto | --all <category> | --set <url> <category>")
        return

    manifest_mod.save_manifest(data, ".")
    dist = Counter(p.get("category") for p in pages if p.get("category"))
    print("Category assignment saved. Distribution:")
    for cat in categories:
        print(f"  {cat}: {dist.get(cat, 0)}")


# --------------------------------------------------------------------------
# generate  (stage 4: produce the injection prompt per page, via Ollama/constants)
# --------------------------------------------------------------------------
def cmd_generate(args):
    try:
        cfg = config_mod.load_config(".")
    except Exception as e:  # noqa: BLE001
        print(str(e), file=sys.stderr)
        sys.exit(1)
    gen = cfg.get("generate") or {}
    constants = (cfg.get("injection") or {}).get("constants") or {}
    data = manifest_mod.load_manifest(".")
    pages = [p for p in data["pages"] if p.get("category")]
    if args.url:
        pages = [p for p in pages if p["url"] == args.url]
    if not pages:
        print("No pages with an assigned category. Run `agentshield configure` first.", file=sys.stderr)
        sys.exit(1)

    print(f"Generating prompts (constants + Ollama {gen.get('model')}) for {len(pages)} page(s) ...")
    ok = skipped = failed = 0
    for p in pages:
        cat = p["category"]
        if p.get("injection_prompt") and not args.force:
            skipped += 1
            print(f"  [{cat}] {p['url']} ... skip (already generated; --force to redo)")
            continue
        try:
            text = generate_for_page(cat, p, gen, constants)
            p["injection_prompt"] = text
            ok += 1
            print(f"  [{cat}] {p['url']} ... ok\n       {text}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  [{cat}] {p['url']} ... FAILED: {e}", file=sys.stderr)
    manifest_mod.save_manifest(data, ".")
    print(f"\nSummary: {ok} generated, {skipped} skipped, {failed} failed.")


# --------------------------------------------------------------------------
# inject  (stage 5, optional: embed prompts into LOCAL static-HTML copies)
# --------------------------------------------------------------------------
def _local_html_for(html_dir, url):
    """Find the pre-built static HTML file for a page's URL path under html_dir."""
    path = urlparse(url).path or "/"
    base = Path(html_dir)
    rel = path.lstrip("/")
    candidates = [
        base / (rel + ".html"),
        base / rel / "index.html",
        base / rel,
    ]
    if path in ("/", ""):
        candidates.insert(0, base / "index.html")
    for c in candidates:
        if c.is_file():
            return c
    return None


def cmd_inject(args):
    try:
        cfg = config_mod.load_config(".")
    except Exception as e:  # noqa: BLE001
        print(str(e), file=sys.stderr)
        sys.exit(1)
    inj = cfg.get("injection") or {}
    methods = inj.get("methods") or ["css", "canvas"]
    html_dir = inj.get("htmlDir") or ""
    data = manifest_mod.load_manifest(".")
    pages = [p for p in data["pages"] if p.get("injection_prompt")]
    if args.url:
        pages = [p for p in pages if p["url"] == args.url]
    if not pages:
        print("No pages have a generated prompt. Run `agentshield generate` first.", file=sys.stderr)
        sys.exit(1)

    if not html_dir:
        print("`inject` embeds prompts into LOCAL static-HTML copies and needs a built site "
              "(set injection.htmlDir to a folder of pre-rendered .html).", file=sys.stderr)
        print("If you deploy via the Node injector instead, use `agentshield export` "
              "to write agentshield.mapping.json.", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(INJECTED_DIR)
    out_dir.mkdir(exist_ok=True)
    print(f"Injecting into local HTML from '{html_dir}' via [{', '.join(methods)}] "
          f"for {len(pages)} page(s) ...")
    ok = failed = 0
    for p in pages:
        src = _local_html_for(html_dir, p["url"])
        if src is None:
            failed += 1
            print(f"  {p['url']} ... FAILED: no HTML found under {html_dir}", file=sys.stderr)
            continue
        try:
            modified = inject_into_html(src.read_text(encoding="utf-8"), p["injection_prompt"], methods)
            fname = f"{_slug(p['url'])}.html"
            (out_dir / fname).write_text(modified, encoding="utf-8")
            p["injected_path"] = f"{INJECTED_DIR}/{fname}"
            ok += 1
            print(f"  [{p.get('category')}] {p['url']} ... -> {p['injected_path']}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  {p['url']} ... FAILED: {e}", file=sys.stderr)
    manifest_mod.save_manifest(data, ".")
    print(f"\nSummary: {ok} injected, {failed} failed. Copies in {INJECTED_DIR}/.")


# --------------------------------------------------------------------------
# export  (manifest -> mapping.json for the Node injection middleware)
# --------------------------------------------------------------------------
def cmd_export(args):
    try:
        cfg = config_mod.load_config(".")
    except Exception as e:  # noqa: BLE001
        print(str(e), file=sys.stderr)
        sys.exit(1)
    methods = (cfg.get("injection") or {}).get("methods") or ["css", "canvas"]
    data = manifest_mod.load_manifest(".")
    pages = [p for p in data["pages"] if p.get("injection_prompt")]
    if not pages:
        print("No pages have a generated prompt. Run `agentshield generate` first.", file=sys.stderr)
        sys.exit(1)

    mapping = {}
    for p in pages:
        path = urlparse(p["url"]).path or p["url"] or "/"
        mapping[path] = {
            "url": p["url"],
            "category": p.get("category"),
            "prompt": p["injection_prompt"],
            "methods": methods,
            "html": build_markup(p["injection_prompt"], methods),
        }
    out = args.out or "agentshield.mapping.json"
    Path(out).write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    print(f"Exported {len(mapping)} injection(s) -> {out}")
    print("Point the Node injection middleware/proxy at this file.")


# --------------------------------------------------------------------------
# verify  (confirm the manifest's route paths match the live site, and that
#          injection lands via the proxy)
# --------------------------------------------------------------------------
def _http_get(url, timeout=15):
    """GET a URL. Returns (status_code|None, body_text). status is None on a transport error."""
    req = urllib.request.Request(url, headers={"User-Agent": "AgentShield-verify"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.getcode(), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:  # noqa: BLE001 - report unreachable as a failed check, don't crash
        return None, str(e)


def cmd_verify(args):
    data = manifest_mod.load_manifest(".")
    pages = data["pages"]
    if not pages:
        print("Manifest has no pages. Run `agentshield add` first.", file=sys.stderr)
        sys.exit(1)

    site = args.site.rstrip("/")
    proxy = args.proxy.rstrip("/") if args.proxy else None
    print(f"Verifying {len(pages)} route(s) against {site}"
          + (f"  (injection via {proxy})" if proxy else "") + " ...\n")

    route_ok = route_bad = inj_ok = inj_bad = 0
    for p in pages:
        path = urlparse(p["url"]).path or p["url"] or "/"
        status, _ = _http_get(site + path)
        if status == 200:
            route_ok += 1
            mark = "route 200"
        else:
            route_bad += 1
            mark = f"route {status or 'UNREACHABLE'}  <- path not served (mismatch?)"
        line = f"  [{mark:<42}] {path}"

        # Injection check: only meaningful for pages that have a prompt, via the proxy.
        if proxy and p.get("injection_prompt"):
            pstatus, pbody = _http_get(proxy + path)
            injected = pstatus == 200 and (CSS_CLASS in pbody or 'id="ashid"' in pbody)
            if injected:
                inj_ok += 1
                line += "  | inject OK"
            else:
                inj_bad += 1
                line += f"  | inject MISSING (proxy {pstatus or 'UNREACHABLE'})"
        print(line)

    print(f"\nRoutes: {route_ok} ok, {route_bad} mismatched.", end="")
    if proxy:
        print(f"  Injection: {inj_ok} present, {inj_bad} missing.")
    else:
        print("  (pass --proxy <url> to also confirm injection lands.)")
    if route_bad or inj_bad:
        print("\nSome checks failed - see the lines above. A mismatched route means the path the "
              "adapter produced isn't what your site serves; fix `pathTemplate`/`slug` (or `url`).",
              file=sys.stderr)
        sys.exit(1)
    print("All checks passed.")


def main():
    parser = argparse.ArgumentParser(
        prog="agentshield",
        description="Read a site's local products/articles and inject hidden agent-directed prompts.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="write agentshield.config.json template")
    p_init.add_argument("-f", "--force", action="store_true", help="overwrite existing config")
    p_init.set_defaults(func=cmd_init)

    p_add = sub.add_parser("add", help="enumerate the site's local product/article pages")
    p_add.add_argument("path", nargs="?", default=None,
                       help="website project dir (overrides source.root in the config)")
    p_add.add_argument("--dry", action="store_true", help="print without writing the manifest")
    p_add.set_defaults(func=cmd_add)

    p_ext = sub.add_parser("extract", help="fill each page's content from the local source")
    p_ext.add_argument("path", nargs="?", default=None,
                       help="website project dir (overrides source.root in the config)")
    p_ext.add_argument("--dry", action="store_true", help="print without writing")
    p_ext.add_argument("--url", help="extract only this one URL from the manifest")
    p_ext.add_argument("--force", action="store_true",
                       help="re-extract all pages (default skips already-extracted ones)")
    p_ext.set_defaults(func=cmd_extract)

    p_cfg = sub.add_parser("configure", help="assign an injection category to each page")
    p_cfg.add_argument("-i", "--interactive", action="store_true",
                       help="prompt for each page's category (default in a terminal)")
    p_cfg.add_argument("--auto", action="store_true",
                       help="round-robin assign all categories across pages")
    p_cfg.add_argument("--all", metavar="CATEGORY", help="assign one category to every page")
    p_cfg.add_argument("--set", nargs=2, metavar=("URL", "CATEGORY"),
                       help="assign a category to a single page")
    p_cfg.set_defaults(func=cmd_configure)

    p_gen = sub.add_parser("generate", help="generate the injection prompt per assigned page (Ollama)")
    p_gen.add_argument("--url", help="only this URL")
    p_gen.add_argument("--force", action="store_true", help="regenerate even if a prompt already exists")
    p_gen.set_defaults(func=cmd_generate)

    p_inj = sub.add_parser("inject", help="embed prompts into local static-HTML copies (css/canvas)")
    p_inj.add_argument("--url", help="only this URL")
    p_inj.set_defaults(func=cmd_inject)

    p_exp = sub.add_parser("export", help="export a mapping.json for the Node injection middleware")
    p_exp.add_argument("--out", help="output path (default agentshield.mapping.json)")
    p_exp.set_defaults(func=cmd_export)

    p_ver = sub.add_parser("verify",
                           help="check the manifest's route paths match your live site (and, with "
                                "--proxy, that injection actually lands)")
    p_ver.add_argument("site", help="base URL of your running site, e.g. http://localhost:8100")
    p_ver.add_argument("--proxy", metavar="URL",
                       help="base URL of the injector proxy, to also confirm the prompt is injected")
    p_ver.set_defaults(func=cmd_verify)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
