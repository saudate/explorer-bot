"""
investigate_with_locators.py — Generate test cases + locator artifacts per TC
Usage:
    python investigate_with_locators.py <url> [output-dir] [count] [complexity]

Same as investigate.py but additionally saves for each TC:
    TC-001_locators.yaml  — all interactive element refs with names and roles
    TC-001_dom.html       — full page HTML structure
    TC-001_screenshot.png — annotated screenshot of the page

Test cases themselves do NOT contain refs — they are human-readable.
Refs and DOM are in separate artifact files for developers/automation engineers.

Arguments:
    url         — page URL to investigate (required)
    output-dir  — folder for output files (default: ./test-cases)
    count       — number of test cases to generate, 1-10 (default: 10)
    complexity  — simple / medium / e2e (default: medium)

Complexity levels:
    simple  — 2-3 steps, UI/navigation checks
    medium  — 4-5 steps, functional tests
    e2e     — as many steps as needed to complete the full logical flow (10-20+)

Reads AI_GATEWAY_API_KEY and AI_GATEWAY_MODEL from .env file or environment.
"""

import sys
import os
import re
import json
import time
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

# ── Args & config ─────────────────────────────────────────────────────────────

URL        = sys.argv[1] if len(sys.argv) > 1 else None
OUTPUT_DIR = sys.argv[2] if len(sys.argv) > 2 else "./test-cases"
TC_COUNT   = int(sys.argv[3]) if len(sys.argv) > 3 else 10
COMPLEXITY = sys.argv[4].lower() if len(sys.argv) > 4 else "medium"

TC_COUNT   = max(1, min(10, TC_COUNT))
COMPLEXITY = COMPLEXITY if COMPLEXITY in ("simple", "medium", "e2e") else "medium"
API_KEY    = os.environ.get("AI_GATEWAY_API_KEY", "")
MODEL      = os.environ.get("AI_GATEWAY_MODEL", "openai/gpt-4o-mini")

if not URL:
    print("Usage: python investigate_with_locators.py <url> [output-dir] [count] [complexity]")
    sys.exit(1)

if not API_KEY:
    print("Error: AI_GATEWAY_API_KEY not set in .env or environment")
    sys.exit(1)

Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

safe_name = re.sub(r'https?://', '', URL)
safe_name = re.sub(r'[^a-zA-Z0-9]', '_', safe_name)
safe_name = re.sub(r'_+', '_', safe_name).strip('_')[:60]

SESSION = f"inv{datetime.now().strftime('%H%M%S')}"
TMP_DIR = os.environ.get("TEMP", ".")

print("━" * 60)
print(f"  URL:        {URL}")
print(f"  Output:     {OUTPUT_DIR}")
print(f"  Model:      {MODEL}")
print(f"  Count:      {TC_COUNT}")
print(f"  Complexity: {COMPLEXITY}")
print(f"  Mode:       with locator artifacts")
print("━" * 60)

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_tmp():
    return os.path.join(TMP_DIR, f"ab_{SESSION}_{int(time.time()*1000)}.txt")

def ab(cmd_args):
    tmp = get_tmp()
    os.system(f'agent-browser {cmd_args} --json > "{tmp}" 2>&1')
    time.sleep(0.5)
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
    time.sleep(0.5)
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
        snap = re.sub(r'\s*\[ref=e\d+\]', '', snap)
        return snap
    except Exception:
        return raw

def get_snapshot_with_refs():
    """Get snapshot keeping refs — for locator artifacts"""
    raw = ab_raw(f'--session {SESSION} snapshot -c')
    try:
        return json.loads(raw).get("data", {}).get("snapshot", "")
    except Exception:
        return raw

def get_interactive():
    raw = ab_raw(f'--session {SESSION} snapshot -i')
    try:
        return json.loads(raw).get("data", {}).get("refs", {})
    except Exception:
        return {}

def get_page_html():
    """Get full page HTML via eval"""
    tmp = get_tmp()
    os.system(f'agent-browser --session {SESSION} eval "document.documentElement.outerHTML" --json > "{tmp}" 2>&1')
    time.sleep(0.5)
    try:
        with open(tmp, encoding="utf-8", errors="replace") as f:
            raw = f.read().strip()
        try: os.unlink(tmp)
        except: pass
        for line in reversed(raw.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                r = json.loads(line)
                return r.get("data", {}).get("result", "") or ""
    except Exception:
        pass
    return ""

# ── Step 1: Open page ─────────────────────────────────────────────────────────

print(f"\n[1/5] Opening page...")
r = ab(f'--session {SESSION} open "{URL}"')
print(f"  {r.get('data', {}).get('title', '...')}")
ab(f'--session {SESSION} wait --load networkidle')

# ── Step 2: Collect page data + artifacts ─────────────────────────────────────

print(f"\n[2/5] Collecting page data and artifacts...")

r = ab(f'--session {SESSION} get title')
PAGE_TITLE = r.get("data", {}).get("title", "Unknown")
print(f"  Title: {PAGE_TITLE}")

SNAPSHOT_INITIAL = get_snapshot()
SNAPSHOT_WITH_REFS = get_snapshot_with_refs()
print(f"  Snapshot: {len(SNAPSHOT_INITIAL)} chars")

interactive = get_interactive()
inputs     = {k: v for k, v in interactive.items() if v.get("role") in ("textbox", "spinbutton")}
buttons    = {k: v for k, v in interactive.items() if v.get("role") == "button"}
checkboxes = {k: v for k, v in interactive.items() if v.get("role") == "checkbox"}
selects    = {k: v for k, v in interactive.items() if v.get("role") in ("combobox", "listbox")}
links      = {k: v for k, v in interactive.items() if v.get("role") == "link"}

print(f"  Found: {len(inputs)} inputs, {len(buttons)} buttons, "
      f"{len(checkboxes)} checkboxes, {len(selects)} selects, {len(links)} links")

# Take annotated screenshot
SCREENSHOT_PATH = os.path.join(OUTPUT_DIR, f"{safe_name}_screenshot.png")
ab(f'--session {SESSION} screenshot --annotate "{SCREENSHOT_PATH}"')
print(f"  Screenshot: {os.path.basename(SCREENSHOT_PATH)}")

# Get page HTML
PAGE_HTML = get_page_html()
print(f"  HTML: {len(PAGE_HTML)} chars")

# Build locators YAML content
def build_locators_yaml(tc_id, tc_title):
    lines = [
        f"# Locators for {tc_id}: {tc_title}",
        f"# URL: {URL}",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"page:",
        f"  url: \"{URL}\"",
        f"  title: \"{PAGE_TITLE}\"",
        f"",
        f"elements:",
    ]
    for ref, info in interactive.items():
        role = info.get("role", "")
        name = info.get("name", "").replace('"', "'")
        if role in ("textbox", "spinbutton", "button", "checkbox", "combobox", "listbox", "link"):
            lines.append(f"  - ref: \"{ref}\"")
            lines.append(f"    role: \"{role}\"")
            lines.append(f"    name: \"{name}\"")
    lines.append("")
    lines.append("# Accessibility snapshot with refs:")
    lines.append("# ---")
    for line in SNAPSHOT_WITH_REFS.splitlines()[:50]:
        lines.append(f"# {line}")
    return "\n".join(lines)

# ── Step 3: Exploration ───────────────────────────────────────────────────────

print(f"\n[3/5] Exploring page interactions...")

OBSERVATIONS = []

def observe(label, snapshot):
    trimmed = snapshot[:400] if len(snapshot) > 400 else snapshot
    OBSERVATIONS.append(f"### {label}\n```\n{trimmed}\n```")
    print(f"  Observed: {label} ({len(snapshot)} chars)")

def find_submit_btn():
    for ref, info in buttons.items():
        name = info.get("name", "").lower()
        if any(w in name for w in ("submit", "check", "save", "send", "create", "register", "sign up", "sign-up", "continue", "next", "go", "ok")):
            return ref, info.get("name", ref)
    for ref, info in buttons.items():
        name = info.get("name", "").lower()
        if not any(w in name for w in ("file", "upload", "browse", "choose", "cookie", "cookies", "accept", "decline", "close", "dismiss", "cancel")):
            return ref, info.get("name", ref)
    return None, None

# Scenario 1: Happy path
if inputs or buttons:
    print(f"\n  Scenario 1: Happy path — fill valid data and submit")
    for ref, info in inputs.items():
        ab(f'--session {SESSION} fill @{ref} "Hello World Test"')
        time.sleep(0.3)
        print(f"    Filled '{info.get('name', ref)}' with 'Hello World Test'")
    for ref, info in checkboxes.items():
        ab(f'--session {SESSION} check @{ref}')
        time.sleep(0.3)
        print(f"    Checked '{info.get('name', ref)}'")

    observe("Page state after filling all fields with valid data", get_snapshot())

    submit_btn, submit_name = find_submit_btn()
    if submit_btn:
        ab(f'--session {SESSION} click @{submit_btn}')
        time.sleep(1.5)
        print(f"    Clicked button '{submit_name}'")
        observe(f"Page state after clicking '{submit_name}' with valid data", get_snapshot())
        body = str(ab(f'--session {SESSION} get text body').get("data", "") or "")
        if body:
            observe("Full page text after submit", body[:800])

# Scenario 2: Empty submit
if inputs and buttons:
    print(f"\n  Scenario 2: Negative — empty required fields")
    ab(f'--session {SESSION} open "{URL}"')
    ab(f'--session {SESSION} wait --load networkidle')
    time.sleep(0.5)
    btn_ref, btn_name = find_submit_btn()
    if btn_ref:
        ab(f'--session {SESSION} click @{btn_ref}')
        time.sleep(1.5)
        print(f"    Clicked '{btn_name}' with empty fields")
        observe("Page state after empty submit", get_snapshot())
        body = str(ab(f'--session {SESSION} get text body').get("data", "") or "")
        if body:
            observe("Page text after empty submit (validation messages)", body[:800])

# Scenario 3: Special characters
if inputs and buttons:
    print(f"\n  Scenario 3: Edge case — special characters")
    ab(f'--session {SESSION} open "{URL}"')
    ab(f'--session {SESSION} wait --load networkidle')
    time.sleep(0.5)
    for ref, info in inputs.items():
        ab(f'--session {SESSION} fill @{ref} "!@#$%^&*()"')
        time.sleep(0.3)
        print(f"    Filled '{info.get('name', ref)}' with special chars")
    btn_ref, btn_name = find_submit_btn()
    if btn_ref:
        ab(f'--session {SESSION} click @{btn_ref}')
        time.sleep(1.5)
        observe("Page state after submitting special characters", get_snapshot())
        body = str(ab(f'--session {SESSION} get text body').get("data", "") or "")
        if body:
            observe("Page text after special chars submit", body[:800])

# Scenario 4: Whitespace only
if inputs and buttons:
    print(f"\n  Scenario 4: Edge case — whitespace only input")
    ab(f'--session {SESSION} open "{URL}"')
    ab(f'--session {SESSION} wait --load networkidle')
    time.sleep(0.5)
    for ref, info in inputs.items():
        ab(f'--session {SESSION} fill @{ref} "   "')
        time.sleep(0.3)
        print(f"    Filled '{info.get('name', ref)}' with whitespace only")
    btn_ref, btn_name = find_submit_btn()
    if btn_ref:
        ab(f'--session {SESSION} click @{btn_ref}')
        time.sleep(1.5)
        observe("Page state after submitting whitespace-only input", get_snapshot())
        body = str(ab(f'--session {SESSION} get text body').get("data", "") or "")
        if body:
            observe("Page text after whitespace submit", body[:800])

ab(f'--session {SESSION} close')
print(f"\n  Total observations: {len(OBSERVATIONS)}")

# ── Step 4: Generate test cases via AI ───────────────────────────────────────

print(f"\n[4/5] Generating test cases with AI ({MODEL})...")

import urllib.request
import urllib.error

observations_text = "\n\n".join(OBSERVATIONS) if OBSERVATIONS else "No interactions recorded."

if COMPLEXITY == "simple":
    complexity_rules = (
        f"## Complexity: SIMPLE\n\n"
        f"Generate SHORT test cases focused on UI checks and navigation:\n"
        f"- 2-3 steps per test case maximum\n"
        f"- Focus on: element visibility, correct labels, links redirect to right pages\n"
    )
    steps_instruction = "2-3 steps per test case"
    example_tc = (
        f"### TC-001: Submit Button Is Visible and Enabled\n\n"
        f"| Field | Value |\n|-------|-------|\n"
        f"| **ID** | TC-001 |\n| **Title** | Submit button is visible and clickable |\n"
        f"| **Priority** | High |\n| **Type** | UI |\n| **Preconditions** | Page is loaded |\n\n"
        f"**Steps:**\n1. Navigate to {URL}\n2. Locate the Submit button\n3. Verify it is visible and enabled\n\n"
        f"**Expected Result:** The Submit button is visible and enabled.\n\n"
        f"**Actual Result:** _{{leave blank}}_\n\n**Status:** _{{Pass / Fail / Not Run}}_\n\n---"
    )

elif COMPLEXITY == "e2e":
    complexity_rules = (
        f"## Complexity: E2E (End-to-End)\n\n"
        f"Generate LONG end-to-end test cases covering complete user flows:\n"
        f"- As many steps as needed to complete the full logical scenario — can be 10, 15, or even 20+ steps\n"
        f"- Do NOT artificially limit steps — a test case ends when the logical flow is complete\n"
        f"- Include setup, main actions, verification, and teardown steps\n"
        f"- Cover multi-step flows: fill form → submit → verify result → navigate → return → verify state\n"
        f"- Include both happy path and recovery from errors in the same flow\n"
        f"- Each step is a single atomic action with exact values and element names\n"
    )
    steps_instruction = "as many steps as needed (10-20+) to complete the full logical flow"
    example_tc = (
        f"### TC-001: Complete Registration Flow with Validation Recovery\n\n"
        f"| Field | Value |\n|-------|-------|\n"
        f"| **ID** | TC-001 |\n| **Title** | Full registration flow including error recovery |\n"
        f"| **Priority** | High |\n| **Type** | E2E |\n"
        f"| **Preconditions** | Browser open, no active session, page accessible |\n\n"
        f"**Steps:**\n"
        f"1. Navigate to {URL}\n2. Verify heading and form elements are visible\n"
        f"3. Click submit without filling fields\n4. Note all validation errors\n"
        f"5. Fill email with invalid format\n6. Fill all other fields with valid data\n"
        f"7. Click submit\n8. Verify email validation error appears\n"
        f"9. Correct the email to a valid address\n10. Click submit again\n"
        f"11. Verify success state or next step\n12. Navigate away\n"
        f"13. Return via browser back\n14. Verify form is reset to empty state\n\n"
        f"**Expected Result:** Form validates correctly at each step, accepts valid data, "
        f"and resets after navigation.\n\n"
        f"**Actual Result:** _{{leave blank}}_\n\n**Status:** _{{Pass / Fail / Not Run}}_\n\n---"
    )

else:  # medium
    complexity_rules = (
        f"## Complexity: MEDIUM\n\n"
        f"Generate standard professional test cases:\n"
        f"- 4-5 steps per test case\n"
        f"- Focus on: form validation, button actions, input handling, navigation\n"
    )
    steps_instruction = "4-5 steps per test case"
    example_tc = (
        f"### TC-001: Empty Required Field Shows Validation Error\n\n"
        f"| Field | Value |\n|-------|-------|\n"
        f"| **ID** | TC-001 |\n| **Title** | Empty required field triggers validation error |\n"
        f"| **Priority** | High |\n| **Type** | Negative / Form |\n"
        f"| **Preconditions** | Page is loaded, all fields are empty |\n\n"
        f"**Steps:**\n1. Navigate to {URL}\n2. Leave all fields empty\n"
        f"3. Click the submit button\n4. Observe validation messages\n\n"
        f"**Expected Result:** Validation error appears. Form not submitted.\n\n"
        f"**Actual Result:** _{{leave blank}}_\n\n**Status:** _{{Pass / Fail / Not Run}}_\n\n---"
    )

PROMPT = (
    f"You are a senior QA engineer writing an Acceptance Test Specification (ATS).\n\n"
    f"Page URL: {URL}\n"
    f"Page Title: {PAGE_TITLE}\n\n"
    f"## Initial page structure\n\n"
    f"```\n{SNAPSHOT_INITIAL[:2000]}\n```\n\n"
    f"## Real interactions performed on the page and their results\n\n"
    f"Use these REAL observations to write accurate Expected Results:\n\n"
    f"{observations_text}\n\n"
    f"{complexity_rules}\n\n"
    f"## General rules\n\n"
    f"- Write as a professional QA engineer — NO mention of tools, automation, scripts, or AI\n"
    f"- Steps describe what the user DOES (clicks, types, selects, submits)\n"
    f"- Expected Result must be based on WHAT WAS ACTUALLY OBSERVED above — be specific\n"
    f"- Use exact element names from the page structure above\n"
    f"- NEVER include refs like ref=e1, ref=e17 — use human-readable names only\n\n"
    f"## Example:\n\n{example_tc}\n\n"
    f"## Format for every test case:\n\n"
    f"### TC-001: Test Case Title\n\n"
    f"| Field | Value |\n|-------|-------|\n"
    f"| **ID** | TC-001 |\n| **Title** | Short descriptive title |\n"
    f"| **Priority** | High / Medium / Low |\n"
    f"| **Type** | Functional / UI / Navigation / Form / Negative / Accessibility / E2E |\n"
    f"| **Preconditions** | Specific state required before running this test |\n\n"
    f"**Steps:**\n1. ({steps_instruction})\n\n"
    f"**Expected Result:** Specific system response based on real observed behavior\n\n"
    f"**Actual Result:** _{{leave blank}}_\n\n"
    f"**Status:** _{{Pass / Fail / Not Run}}_\n\n---\n\n"
    f"Generate EXACTLY {TC_COUNT} test cases numbered TC-001 through TC-{TC_COUNT:03d}."
)

print("  Calling AI via Vercel Gateway API...")
text = ""
try:
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": 8000,
        "temperature": 0.3
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://ai-gateway.vercel.sh/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    text = result["choices"][0]["message"]["content"]
except urllib.error.HTTPError as e:
    print(f"  HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}")
except Exception as e:
    print(f"  API error: {e}")

print(f"  Generated: {len(text)} chars")

if not text:
    print("  Warning: No AI response.")
    text = "# No AI response\n\nCheck AI_GATEWAY_API_KEY and AI_GATEWAY_MODEL."

# ── Step 5: Save TC files + artifacts ────────────────────────────────────────

print(f"\n[5/5] Saving files...")

date_str      = datetime.now().strftime("%Y-%m-%d %H:%M")
combined_path = os.path.join(OUTPUT_DIR, f"{safe_name}_all_testcases.md")

with open(combined_path, "w", encoding="utf-8") as f:
    f.write(f"# Test Cases: {PAGE_TITLE}\n**URL:** {URL}\n**Date:** {date_str}\n\n---\n\n")
    f.write(text)
print(f"  Combined: {os.path.basename(combined_path)}")

# Split into individual TC files + save artifacts per TC
pattern = r'(### TC-\d+:.*?)(?=### TC-\d+:|\Z)'
matches = re.findall(pattern, text, re.DOTALL)

count = 0
if matches:
    for tc in matches:
        tc = tc.strip()
        if not tc:
            continue
        header = re.match(r'### (TC-\d+):\s*(.+)', tc)
        if not header:
            continue
        tc_id    = header.group(1)           # TC-001
        tc_title = header.group(2).strip()
        safe_title = re.sub(r'[^a-zA-Z0-9\s]', '', tc_title)
        safe_title = re.sub(r'\s+', '_', safe_title.strip())[:50]
        base_name  = f"{tc_id}_{safe_title}"

        # 1. Save TC markdown
        md_path = os.path.join(OUTPUT_DIR, f"{base_name}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"**URL:** {URL}\n\n")
            f.write(tc + "\n")
        print(f"  {base_name}.md")

        # 2. Save locators YAML
        yaml_path = os.path.join(OUTPUT_DIR, f"{base_name}_locators.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(build_locators_yaml(tc_id, tc_title))
        print(f"  {base_name}_locators.yaml")

        # 3. Save DOM HTML (shared, copy per TC)
        html_path = os.path.join(OUTPUT_DIR, f"{base_name}_dom.html")
        if PAGE_HTML:
            with open(html_path, "w", encoding="utf-8", errors="replace") as f:
                f.write(PAGE_HTML)
            print(f"  {base_name}_dom.html")

        # 4. Copy screenshot per TC
        import shutil
        if os.path.exists(SCREENSHOT_PATH):
            tc_screenshot = os.path.join(OUTPUT_DIR, f"{base_name}_screenshot.png")
            shutil.copy2(SCREENSHOT_PATH, tc_screenshot)
            print(f"  {base_name}_screenshot.png")

        count += 1
else:
    print("  Could not split — all test cases in combined file")

# ── Summary ───────────────────────────────────────────────────────────────────

print("\n" + "━" * 60)
print(f"  Done! {count} TCs, each with: .md + _locators.yaml + _dom.html + _screenshot.png")
print(f"  Output: {OUTPUT_DIR}")
print("━" * 60)
