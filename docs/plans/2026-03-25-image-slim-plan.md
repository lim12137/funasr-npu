# Image Slim Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce runtime Docker image size without changing runtime behavior.

**Architecture:** Use multi-stage build: builder installs deps and clones Fun-ASR-GGUF, runtime copies only needed artifacts. Keep model volume mount, avoid bundling tests/docs.

**Tech Stack:** Docker, Ubuntu 22.04 base, Python 3.11, pip.

---

### Task 1: Record baseline image size

**Files:**
- None

**Step 1: Pull baseline image (if available)**

Run: `docker pull ghcr.io/lim12137/funasr-npu:sha-7041f73`  
Expected: Pull succeeds or fails (if not accessible).

**Step 2: Record size via image list**

Run: `docker image ls ghcr.io/lim12137/funasr-npu:sha-7041f73`  
Expected: Size column available.

**Step 3: Fallback to manifest size**

Run: `docker manifest inspect ghcr.io/lim12137/funasr-npu:sha-7041f73`  
Expected: Output includes layer sizes (sum for baseline).

### Task 2: Split runtime vs dev requirements

**Files:**
- Modify: `requirements.txt`
- Create: `requirements-dev.txt`

**Step 1: Identify runtime packages**

Run: `Get-Content requirements.txt`  
Expected: Contains `pytest` (to be removed).

**Step 2: Move dev-only deps**

Action: Remove `pytest` from `requirements.txt`, add to `requirements-dev.txt`.

### Task 3: Reduce build context

**Files:**
- Modify: `.dockerignore`

**Step 1: Add ignore entries**

Action: Add `tests/`, `docs/`, `.pytest_cache/` and other non-runtime content to `.dockerignore`.

### Task 4: Convert Dockerfile to multi-stage

**Files:**
- Modify: `Dockerfile`

**Step 1: Add builder stage**

Action: Install build-only tools (e.g., git), install runtime deps, clone Fun-ASR-GGUF shallow, remove `.git`.

**Step 2: Add runtime stage**

Action: Copy runtime artifacts only (Python packages, server, scripts, repo), keep env/CMD unchanged.

### Task 5: Build new image and compare size

**Files:**
- None

**Step 1: Build local image**

Run: `docker build -t funasr-npu:local .`  
Expected: Build succeeds.

**Step 2: Record new size**

Run: `docker image ls funasr-npu:local`  
Expected: Size column available; should be smaller than baseline.

### Task 6: Run container to verify startup

**Files:**
- None

**Step 1: Start container**

Run: `docker run --rm -p 8000:8000 funasr-npu:local`  
Expected: Uvicorn startup log appears.
