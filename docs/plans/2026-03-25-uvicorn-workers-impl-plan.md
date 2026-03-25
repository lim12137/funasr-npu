# Uvicorn Workers Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 `UVICORN_WORKERS` 默认值与限幅逻辑落地到启动脚本，并补齐文档与回归记录。  

**Architecture:** 仅在 `scripts/start-server.sh` 内解析环境变量并裁剪到区间 `[1,4]`，保持进程启动入口不变；文档说明与测试报告补充说明即可。  

**Tech Stack:** Bash, pytest

---

### Task 1: Workers 解析测试与脚本实现

**Files:**
- Create: `tests/test_start_server.py`
- Modify: `scripts/start-server.sh`

**Step 1: Write the failing test**

```python
from pathlib import Path
import re

def test_start_server_workers_logic_present():
    content = Path("scripts/start-server.sh").read_text(encoding="utf-8")
    assert "UVICORN_WORKERS" in content
    assert "DEFAULT_WORKERS=4" in content
    assert "UVICORN_WORKERS//[[:space:]]/" in content
    assert "=~ ^[[:space:]]*$" in content
    assert "=~ ^[[:space:]]*-?[0-9]+[[:space:]]*$" in content
    assert re.search(r"\\(\\(\\s*value\\s*<=\\s*0\\s*\\)\\)", content)
    assert re.search(r"\\(\\(\\s*value\\s*>=\\s*4\\s*\\)\\)", content)
    assert re.search(r"--workers\\s+\\\"?\\$\\{?WORKERS\\}?\\\"?", content)
```

**Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_start_server.py -k workers`  
Expected: FAIL（脚本尚未包含解析逻辑）

**Step 3: Write minimal implementation**

```bash
DEFAULT_WORKERS=4
if [[ -z "${UVICORN_WORKERS+x}" ]]; then
  WORKERS="${DEFAULT_WORKERS}"
elif [[ "${UVICORN_WORKERS}" =~ ^[[:space:]]*$ ]]; then
  WORKERS="${DEFAULT_WORKERS}"
elif [[ "${UVICORN_WORKERS}" =~ ^[[:space:]]*-?[0-9]+[[:space:]]*$ ]]; then
  value="${UVICORN_WORKERS//[[:space:]]/}"
  if (( value <= 0 )); then
    WORKERS=1
  elif (( value >= 4 )); then
    WORKERS=4
  else
    WORKERS="${value}"
  fi
else
  echo "[ERROR] UVICORN_WORKERS 必须是整数: ${UVICORN_WORKERS}" >&2
  exit 1
fi
```

**Step 4: Run test to verify it passes**

Run: `pytest -q tests/test_start_server.py -k workers`  
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_start_server.py scripts/start-server.sh
git commit -m "test: cover uvicorn workers parsing"
```

> 备注：按用户要求不执行提交。

---

### Task 2: 文档与回归记录

**Files:**
- Modify: `README.md`
- Modify: `docs/reports/2026-03-25-ws-compat-test.md`

**Step 1: Update README**

新增说明：`UVICORN_WORKERS` 为 uvicorn 多进程 workers，最大 4，空白视为未设置，示例说明如何配置。

**Step 2: Run full regression**

Run: `pytest -q`  
Expected: PASS

**Step 3: Update report**

追加段落“workers 变更回归”，记录命令与关键输出。

**Step 4: Commit**

```bash
git add README.md docs/reports/2026-03-25-ws-compat-test.md
git commit -m "docs: document uvicorn workers env"
```

> 备注：按用户要求不执行提交。
