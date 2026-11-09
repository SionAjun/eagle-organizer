"""Register this server as "eagle" in Claude Desktop's config, then check Eagle.

Usage (run by install.ps1):  uv run --frozen register_desktop.py <uv.exe path> <server dir>
"""
import glob
import json
import os
import shutil
import sys
import time
import urllib.request

NAME = "eagle"


def config_paths():
    appdata = os.environ.get("APPDATA", "")
    local = os.environ.get("LOCALAPPDATA", "")
    found = []
    std = os.path.join(appdata, "Claude", "claude_desktop_config.json")
    if os.path.isfile(std):
        found.append(std)
    found += glob.glob(os.path.join(local, "Packages", "Claude_*", "LocalCache", "Roaming", "Claude", "claude_desktop_config.json"))
    return found or [std]


def register(uv_path, server_dir):
    entry = {
        "command": uv_path,
        "args": ["--directory", server_dir, "run", "--frozen", "main.py"],
        "env": {"PYTHONIOENCODING": "utf-8"},
    }
    for path in config_paths():
        cfg = {}
        if os.path.isfile(path):
            backup = f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
            shutil.copy2(path, backup)
            print(f"  已备份: {backup}")
            with open(path, encoding="utf-8-sig") as f:
                text = f.read().strip()
            cfg = json.loads(text) if text else {}
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        servers = cfg.setdefault("mcpServers", {})
        action = "更新" if NAME in servers else "新增"
        servers[NAME] = entry
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print(f"  {action} \"{NAME}\" -> {path}")
        print(f"  现有 MCP: {', '.join(servers)}")


def check_eagle():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open("http://localhost:41595/api/application/info", timeout=3) as r:
            data = json.load(r).get("data", {})
        print(f"  Eagle 在运行: 版本 {data.get('version')} ({data.get('platform')})")
    except Exception:
        print("  Eagle 现在没开（不影响安装，用的时候开着就行）")


if __name__ == "__main__":
    register(sys.argv[1], os.path.abspath(sys.argv[2]))
    check_eagle()
