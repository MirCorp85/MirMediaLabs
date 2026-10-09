"""Refresh server/static/prompt_guides.json from Comfy's official per-model prompting guides.

Dev-time only — never called at render time. Talks to the Comfy Cloud MCP (discovery tools are free,
no generation is ever submitted) and writes the MML copy plus the MirOS mirror.

    set COMFY_API_KEY=comfyui-...        (platform.comfy.org → API keys)
    C:\\AiMir-Tools\\comfy-agent-venv\\Scripts\\python.exe tools\\refresh_prompt_guides.py [--dry]

Without an API key, ask Claude Code (signed in to the comfy-cloud MCP) to run get_prompting_guide for
each family below and save the same JSON shape.
"""
import asyncio
import datetime
import json
import os
import re
import sys

URL = "https://cloud.comfy.org/mcp"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = [os.path.join(HERE, "..", "server", "static", "prompt_guides.json"),
       os.environ.get("MML_GUIDES_MIRROR", "")]   # optional local mirror copy (env var, never a hardcoded path; skipped if unset)

# our builder key → model family names to try with get_prompting_guide (first hit wins)
FAMILIES = {
    "qwen_t2i": ["qwen-image", "Qwen-Image"],
    "qwen_edit": ["qwen-image-edit", "Qwen-Image-Edit"],
    "h3": ["minimax-h3", "MiniMax H3", "hailuo"],
    "h3_refs": ["minimax-h3", "MiniMax H3", "hailuo"],
    "music3": ["minimax-music-3", "minimax music"],
    "ace": ["ace-step", "ace step 1.5", "ace"],
    "sdxl": ["sdxl", "SDXL"],
    "flux": ["flux", "Flux"],
    "wan": ["wan", "Wan"],
}
TABLE_COLS = {"steps": int, "cfg": float, "sampler": str, "scheduler": str, "resolution": str}
# guide lines about runtime/settings plumbing — useful to us, noise to the prompt-rewriting engine
NOT_PROMPT = re.compile(r"\b(lora|template|checkpoint|vram|loader|steps?|cfg|sampler|scheduler|shift|int8|bf16|fp8|nvfp4|node)\b", re.I)


def parse(text):
    """Official guide markdown → prompt rules (Tips + Common mistakes, prompt-relevant only) + settings table."""
    rules, settings, section = [], {}, ""
    lines = [ln.strip() for ln in text.splitlines()]
    for i, ln in enumerate(lines):
        if ln.startswith("#"):
            section = ln.lstrip("#").strip().lower()
            continue
        m = re.match(r"^- \*\*(Negative prompt|Prompt weights)[^*]*\*\*:?\s*(.+)$", ln)
        if m:
            rules.append("%s: %s" % (re.sub(r"\s*\(.*?\)", "", m.group(1)), m.group(2).strip("` ")))
            continue
        if ln.startswith("| steps") and i + 2 < len(lines):
            cells = [c.strip() for c in lines[i + 2].strip("|").split("|")]
            for (k, cast), v in zip(TABLE_COLS.items(), cells):
                try:
                    settings[k] = cast(v)
                except ValueError:
                    pass
            continue
        m = re.match(r"^[-*] (.+)$", ln)
        if m and section in ("tips", "common mistakes") and not NOT_PROMPT.search(m.group(1)):
            rules.append(m.group(1).replace("**", ""))
    return rules[:20], settings


def is_guide(text, name):
    """The server falls back to a different playbook (or 'no guide matched') for unknown names — reject those."""
    head = text[:200].lower()
    return "prompting & settings guide" in head and "no prompting guide matched" not in head


async def fetch(session, names):
    tools = {t.name: t for t in (await session.list_tools()).tools}
    tool = tools.get("get_prompting_guide")
    if not tool:
        sys.exit("get_prompting_guide not offered by the server — tools: %s" % ", ".join(sorted(tools)))
    arg = next(iter((getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None) or {}).get("properties", {}) or {"model": 0}))
    for name in names:
        res = await session.call_tool(tool.name, {arg: name})
        text = "\n".join(getattr(c, "text", "") for c in res.content)
        if not getattr(res, "is_error", getattr(res, "isError", False)) and is_guide(text, name):
            return name, text
    return None, None


async def main(dry):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    from mcp.shared._httpx_utils import create_mcp_http_client
    key = os.environ.get("COMFY_API_KEY")
    env = os.path.join(HERE, "..", ".env")   # gitignored — never in the public repo
    if not key and os.path.isfile(env):
        for line in open(env, encoding="utf-8"):
            if line.startswith("COMFY_API_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        sys.exit("COMFY_API_KEY not set (see docstring)")
    guides = {}
    async with create_mcp_http_client(headers={"X-API-Key": key}) as http, \
            streamable_http_client(URL, http_client=http) as streams:
        r, w = streams[0], streams[1]
        async with ClientSession(r, w) as session:
            await session.initialize()
            for k, names in FAMILIES.items():
                fam, text = await fetch(session, names)
                if not text:
                    print("  %-10s no guide" % k)
                    continue
                rules, settings = parse(text)
                guides[k] = {"family": fam, "rules": rules, "settings": settings, "raw": text,
                             "source": "Comfy MCP get_prompting_guide", "fetched": datetime.date.today().isoformat()}
                print("  %-10s %s · %d rules · %s" % (k, fam, len(rules), settings))
    if dry or not guides:
        return
    for path in OUT:
        if os.path.isdir(os.path.dirname(path)):
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"guides": guides}, f, indent=1, ensure_ascii=False)
            print("wrote", os.path.normpath(path))


if __name__ == "__main__":
    asyncio.run(main("--dry" in sys.argv))
