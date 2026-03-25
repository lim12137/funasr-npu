from pathlib import Path
import re


def test_start_server_workers_logic_present():
    content = Path("scripts/start-server.sh").read_text(encoding="utf-8")
    assert "UVICORN_WORKERS" in content
    assert "DEFAULT_WORKERS=4" in content
    assert "UVICORN_WORKERS//[[:space:]]/" in content
    assert "=~ ^[[:space:]]*$" in content
    assert "=~ ^[[:space:]]*-?[0-9]+[[:space:]]*$" in content
    assert re.search(r"\(\(\s*value\s*<=\s*0\s*\)\)", content)
    assert re.search(r"\(\(\s*value\s*>=\s*4\s*\)\)", content)
    assert re.search(r"--workers\s+\"?\$\{?WORKERS\}?\"?", content)
