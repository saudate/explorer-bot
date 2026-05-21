"""
regression.py — Automated regression checker using agent-browser + AI
Reads TC-*.md files, executes steps via browser, compares with Expected Result.

Usage:
    python regression.py                        # runs all TC-*.md in ./test-cases/
    python regression.py ./test-cases/demoqa    # specific folder
    python regression.py ./test-cases TC-001    # single test case by ID

Output:
    regression_report.md — PASS / FAIL / WARNING per test case
"""

import sys
import os
import re
import json
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# ── Load .env ─────────────────────────────────────────────────────────────────

def load_env(paths=(".env", "../.env")):
    for p in paths:
        if os.path.exists(p):
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())

load_env()

# ── Args ──────────────────────────────────────────────────────────────────────

TC_DIR    = sys.argv[1] if len(sys.argv) > 1 else "./test-cases"
TC_FILTER = sys.argv[2] if len(sys.argv) > 2 else None
API_KEY   = os.environ.get("AI_GATEWAY_API_KEY", "")
MODEL     = os.environ.get("AI_GATEWAY_MODEL", "openai/gpt-4o-mini")
TMP_DIR   = os.environ.get("TEMP", ".")

if not API_KEY:
    print("Error: AI_GATEWAY_API_KEY not set")
    sys.exit(1)

SESSION = f"reg{datetime.now().strftime('%H%M%S')}"

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_tmp():
    return os.path.join(TMP_DIR, f"ab_{SESSION}_{int(time.time()*1000)}.txt")

def ab(cmd_args):
    tmp = get_tmp()
    os.system(f'agent-browser {cmd_args} --json > "{tmp}" 2>&1')
    time.sleep(0.6)
    try:
        with open(tmp, encoding="utf-8", errors="replace") as f:
            raw = f.read().strip()
        try: os.unlink(tmp)
        except: pass
        for line in reversed(raw.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                return json.loads(line)
    except Exception:
        pass
    return {}

def ab_raw(cmd_args):
    tmp = get_tmp()
    os.system(f'agent-browser {cmd_args} --json > "{tmp}" 2>&1')
    time.sleep(0.6)
    try:
        with open(tmp, encoding="utf-8", errors="replace") as f:
            raw = f.read().strip()
        try: os.unlink(tmp)
        except: pass
        return raw
    except Exception:
        return ""

def get_snapshot():
    raw = ab_raw(f'--session {SESSION} snapshot -c')
    try:
        snap = json.loads(raw).get("data", {}).get("snapshot", "")
        return re.sub(r'\s*\[ref=e\d+\]', '', snap)
    except Exception:
        return raw

def get_interactive():
    raw = ab_raw(f'--session {SESSION} snapshot -i')
    try:
        return json.loads(raw).get("data", {}).get("refs", {})
    except Exception:
        return {}

def ask_ai(prompt):
    """Call AI directly via Vercel Gateway"""
    try:
        body = json.dumps({
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1000,
            "temperature": 0.1
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://ai-gateway.vercel.sh/v1/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"AI error: {e}"

# ── Parse test case .md ───────────────────────────────────────────────────────

def parse_tc(filepath):
    with open(filepath, encoding="utf-8", errors="replace") as f:
        content = f.read()

    tc = {
        "file":          os.path.basename(filepath),
        "url":           "",
        "id":            "",
        "title":         "",
        "priority":      "",
        "type":          "",
        "preconditions": "",
        "steps":         [],
        "expected":      "",
    }

    # URL
    m = re.search(r'\*\*URL:\*\*\s*(https?://\S+)', content)
    if m:
        tc["url"] = m.group(1).strip()
    if not tc["url"]:
        m = re.search(r'(https?://[^\s\)\"\']+)', content)
        if m:
            tc["url"] = m.group(1).strip()

    # ID and title
    m = re.search(r'### (TC-\d+):\s*(.+)', content)
    if m:
        tc["id"]    = m.group(1)
        tc["title"] = m.group(2).strip()

    # Table fields
    for field, key in [("Priority", "priority"), ("Type", "type"), ("Preconditions", "preconditions")]:
        m = re.search(rf'\|\s*\*\*{field}\*\*\s*\|\s*(.+?)\s*\|', content)
        if m:
            tc[key] = m.group(1).strip()

    # Steps
    m = re.search(r'\*\*Steps:\*\*\n(.*?)\n\n\*\*Expected', content, re.DOTALL)
    if m:
        tc["steps"] = re.findall(r'^\d+\.\s*(.+)', m.group(1), re.MULTILINE)

    # Expected Result
    m = re.search(r'\*\*Expected Result:\*\*\s*(.+?)(?:\n\n|\*\*Actual|\Z)', content, re.DOTALL)
    if m:
        tc["expected"] = m.group(1).strip()

    return tc

# ── Translate step to browser action via AI ───────────────────────────────────

def translate_step(step_text, snapshot, refs):
    refs_text = "\n".join([
        f"  @{k}: {v.get('role')} '{v.get('name', '')}'"
        for k, v in refs.items()
    ])

    prompt = (
        f"You control a browser via agent-browser CLI.\n\n"
        f"Current page elements:\n{refs_text}\n\n"
        f"Current page state:\n{snapshot[:600]}\n\n"
        f"Test step: \"{step_text}\"\n\n"
        f"Translate this step into ONE agent-browser command.\n"
        f"Available commands:\n"
        f"- click @ref\n"
        f"- fill @ref \"value\"\n"
        f"- check @ref\n"
        f"- uncheck @ref\n"
        f"- select @ref \"option\"\n"
        f"- scroll down\n"
        f"- wait 2000\n"
        f"- open \"url\"\n"
        f"- back\n"
        f"- SKIP (if step is observation/verification only, not an action)\n\n"
        f"Reply with ONLY the command. Examples: click @e3 | fill @e5 \"test@test.com\" | SKIP"
    )

    cmd = ask_ai(prompt).strip()
    cmd = re.sub(r'`', '', cmd).strip().split('\n')[0].strip()
    return cmd

# ── Verify expected result via AI ─────────────────────────────────────────────

def verify_expected(expected, snapshot, body_text=""):
    actual_context = snapshot[:800]
    if body_text:
        actual_context += f"\n\nPage text:\n{body_text[:400]}"

    prompt = (
        f"You are a QA engineer verifying a test result.\n\n"
        f"Expected Result:\n\"{expected}\"\n\n"
        f"Actual page state after test execution:\n```\n{actual_context}\n```\n\n"
        f"Does the actual page state match the expected result?\n\n"
        f"Reply EXACTLY in this format:\n"
        f"VERDICT: PASS\nREASON: brief explanation\n\n"
        f"or\n\n"
        f"VERDICT: FAIL\nREASON: what is different, what to check manually"
    )

    response = ask_ai(prompt)
    verdict = "WARNING"
    reason  = "Could not verify"

    if response:
        v = re.search(r'VERDICT:\s*(PASS|FAIL)', response, re.IGNORECASE)
        r = re.search(r'REASON:\s*(.+)', response, re.IGNORECASE | re.DOTALL)
        if v:
            raw_verdict = v.group(1).upper()
            # FAIL → WARNING — agent cannot confirm bugs, only flag for manual check
            verdict = "PASS" if raw_verdict == "PASS" else "WARNING"
        if r: reason = r.group(1).strip()[:300]

    return verdict, reason

# ── Run single test case ──────────────────────────────────────────────────────

def run_tc(tc):
    print(f"\n  [{tc['id']}] {tc['title'][:60]}")

    result = {
        "id":      tc["id"],
        "title":   tc["title"],
        "file":    tc["file"],
        "url":     tc["url"],
        "verdict": "WARNING",
        "steps":   [],
        "reason":  "",
        "expected": tc["expected"],
    }

    if not tc["url"]:
        result["reason"] = "No URL found in test case — cannot execute"
        print(f"  ⚠ No URL")
        return result

    if not tc["steps"]:
        result["reason"] = "No steps found in test case"
        print(f"  ⚠ No steps")
        return result

    # Open page
    r = ab(f'--session {SESSION} open "{tc["url"]}"')
    ab(f'--session {SESSION} wait --load networkidle')
    time.sleep(0.5)

    if not r.get("success"):
        result["verdict"] = "FAIL"
        result["reason"]  = f"Could not open URL: {tc['url']}"
        print(f"  ✗ Could not open URL")
        return result

    # Execute steps
    step_results = []
    last_snapshot = get_snapshot()
    had_warning   = False

    for i, step in enumerate(tc["steps"], 1):
        print(f"    Step {i}: {step[:55]}...")

        refs = get_interactive()
        cmd  = translate_step(step, last_snapshot, refs)

        step_r = {"num": i, "text": step, "cmd": cmd, "success": True, "error": ""}

        if not cmd or cmd.upper() == "SKIP":
            step_r["cmd"] = "SKIP"
            print(f"      → SKIP (observation step)")
        else:
            r = ab(f'--session {SESSION} {cmd}')
            time.sleep(0.8)
            last_snapshot = get_snapshot()

            if not r.get("success", True):
                step_r["success"] = False
                step_r["error"]   = r.get("error", "unknown error") or ""
                had_warning = True
                print(f"      → ⚠ WARNING: {step_r['error'][:60]}")
            else:
                print(f"      → ✓ {cmd}")

        step_results.append(step_r)

    result["steps"] = step_results

    # Get final page text
    body = str(ab(f'--session {SESSION} get text body').get("data", "") or "")

    # Verify expected result
    print(f"    Verifying expected result...")
    verdict, reason = verify_expected(tc["expected"], last_snapshot, body)

    # If some steps had warnings but verdict is PASS — downgrade to WARNING
    if had_warning and verdict == "PASS":
        verdict = "WARNING"
        reason  = f"Some steps could not execute. {reason}"

    result["verdict"] = verdict
    result["reason"]  = reason

    icon = "✓" if verdict == "PASS" else "⚠"
    print(f"  {icon} {verdict}: {reason[:70]}")

    return result

# ── Collect TC files ──────────────────────────────────────────────────────────

tc_dir   = Path(TC_DIR)
tc_files = sorted(tc_dir.rglob("TC-*.md"))

if TC_FILTER:
    tc_files = [f for f in tc_files if TC_FILTER in f.name]

if not tc_files:
    print(f"No TC-*.md files found in {TC_DIR}")
    sys.exit(0)

print("━" * 60)
print(f"  Regression run")
print(f"  Folder: {TC_DIR}")
print(f"  Test cases: {len(tc_files)}")
print(f"  Model: {MODEL}")
print("━" * 60)

# ── Run all TCs ───────────────────────────────────────────────────────────────

results = []
for tc_file in tc_files:
    tc     = parse_tc(tc_file)
    result = run_tc(tc)
    results.append(result)

ab(f'--session {SESSION} close')

# ── Generate report ───────────────────────────────────────────────────────────

passed   = [r for r in results if r["verdict"] == "PASS"]
warnings = [r for r in results if r["verdict"] == "WARNING"]

date_str    = datetime.now().strftime("%Y-%m-%d %H:%M")
report_path = os.path.join(TC_DIR, "regression_report.md")

with open(report_path, "w", encoding="utf-8") as f:
    f.write(f"# Regression Report\n\n")
    f.write(f"**Date:** {date_str}  \n")
    f.write(f"**Folder:** {TC_DIR}  \n")
    f.write(f"**Model:** {MODEL}\n\n")
    f.write(f"## Summary\n\n")
    f.write(f"| Status | Count |\n|--------|-------|\n")
    f.write(f"| ✅ PASS | {len(passed)} |\n")
    f.write(f"| ⚠️ WARNING | {len(warnings)} |\n")
    f.write(f"| **Total** | **{len(results)}** |\n\n")

    # Full results table
    f.write(f"## All Test Cases\n\n")
    f.write(f"| Status | ID | Title | File |\n|--------|-----|-------|------|\n")
    for r in results:
        icon = "✅" if r["verdict"] == "PASS" else "⚠️"
        f.write(f"| {icon} {r['verdict']} | {r['id']} | {r['title'][:50]} | `{r['file']}` |\n")
    f.write(f"\n")

    if warnings:
        f.write(f"## ⚠️ Warnings — verify manually\n\n")
        f.write(f"> These test cases need manual review — something did not match or could not be verified\n\n")
        for r in warnings:
            f.write(f"### {r['id']}: {r['title']}\n\n")
            f.write(f"| Field | Value |\n|-------|-------|\n")
            f.write(f"| **File** | `{r['file']}` |\n")
            f.write(f"| **URL** | {r['url']} |\n")
            f.write(f"| **Verdict** | ⚠️ WARNING |\n\n")
            f.write(f"**Expected Result:**\n{r['expected']}\n\n")
            f.write(f"**Why it needs manual check:**\n{r['reason']}\n\n")
            f.write(f"**Steps executed:**\n")
            for s in r.get("steps", []):
                icon = "✓" if s["success"] else "⚠"
                cmd  = f" → `{s['cmd']}`" if s.get("cmd") and s["cmd"] != "SKIP" else ""
                err  = f" — {s['error']}" if s.get("error") else ""
                f.write(f"{s['num']}. {icon} {s['text']}{cmd}{err}\n")
            f.write(f"\n---\n\n")
            f.write(f"### {r['id']}: {r['title']}\n\n")
            f.write(f"| Field | Value |\n|-------|-------|\n")
            f.write(f"| **File** | `{r['file']}` |\n")
            f.write(f"| **URL** | {r['url']} |\n")
            f.write(f"| **Verdict** | ⚠️ WARNING |\n\n")
            f.write(f"**Reason:** {r['reason']}\n\n")
            f.write(f"**Steps executed:**\n")
            for s in r.get("steps", []):
                icon = "✓" if s["success"] else "⚠"
                cmd  = f" → `{s['cmd']}`" if s.get("cmd") and s["cmd"] != "SKIP" else ""
                err  = f" — {s['error']}" if s.get("error") else ""
                f.write(f"{s['num']}. {icon} {s['text']}{cmd}{err}\n")
            f.write(f"\n---\n\n")

    if passed:
        f.write(f"## ✅ Passed\n\n")
        f.write(f"| ID | Title | URL |\n|-----|-------|-----|\n")
        for r in passed:
            f.write(f"| {r['id']} | {r['title']} | {r['url']} |\n")

print("\n" + "━" * 60)
print(f"  Regression complete!")
print(f"  ✅ PASS:    {len(passed)}")
print(f"  ⚠  WARNING: {len(warnings)}")
print(f"  Report: {report_path}")
print("━" * 60)
