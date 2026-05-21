# 🤖 Explorer Bot — AI-powered QA Test Case Generator

A set of scripts for automated test case generation and regression testing of web pages.  
Scripts open a real browser, explore the page, perform actual interactions, and generate ready-to-use Markdown test cases via AI.

---

## What it does

| Goal | Script |
|------|--------|
| Generate test cases for any web page | `investigate.py` |
| Same + save locators, DOM and screenshot for automation engineers | `investigate_with_locators.py` |
| Check if existing test cases still pass after changes | `regression.py` |
| Clean up the output folder | `clean.py` |

**Typical use cases:**
- QA engineer gets a new page → runs `investigate.py` → has 10 ready test cases in 2 minutes
- After a release, need to verify nothing is broken → runs `regression.py` → gets a PASS/WARNING report
- Automation engineer needs element locators → runs `investigate_with_locators.py` → gets a `.yaml` with all refs

---

## Requirements

- Python 3.8+
- Node.js 18+ (required for `agent-browser`)
- `agent-browser` CLI
- A [Vercel](https://vercel.com) account to get an AI Gateway API key

---

## Step 1 — Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

---

## Step 2 — Install Node.js

If Node.js is not installed yet:

1. Go to [nodejs.org](https://nodejs.org)
2. Download the LTS version (18+)
3. Install it and verify:

```bash
node --version
# v20.x.x or higher
```

---

## Step 3 — Install agent-browser

`agent-browser` is a CLI tool for controlling a browser via commands. Scripts use it to open pages, click elements, fill forms, and capture page state.

```bash
npm install -g agent-browser
```

Verify the installation:

```bash
agent-browser --version
```

> **Note:** `agent-browser` uses Playwright under the hood. On first run it may prompt you to install browsers — accept it.

If browsers were not installed automatically:

```bash
npx playwright install chromium
```

---

## Step 4 — Check Python

```bash
python --version
# Python 3.8 or higher
```

If Python is not installed — download it from [python.org](https://www.python.org/downloads/).

Scripts use only the Python standard library — **no pip packages required**.

---

## Step 5 — Get an AI Gateway API key

Scripts use [Vercel AI Gateway](https://vercel.com/docs/ai-gateway) — a single endpoint for accessing multiple AI models (OpenAI, DeepSeek, Anthropic, and others).

1. Go to [vercel.com](https://vercel.com) and sign up (free)
2. Navigate to **Dashboard → AI Gateway**
3. Create a new Gateway or use an existing one
4. Copy the API key (starts with `vck_...`)

---

## Step 6 — Configure `.env`

Copy the example file:

```bash
cp .env.example .env
```

Or create `.env` manually in the project root:

```env
AI_GATEWAY_API_KEY=vck_your_key_here
AI_GATEWAY_MODEL=openai/gpt-4o-mini
```

> Vercel AI Gateway supports a large number of models from OpenAI, Anthropic, DeepSeek, Mistral, Meta, Google, and others.  
> See the full list at [vercel.com/docs/ai-gateway](https://vercel.com/docs/ai-gateway).

---

## Step 7 — Add `.env` to `.gitignore`

**Important:** never push `.env` with real keys to GitHub.

Make sure `.gitignore` contains:

```
.env
```

If there is no `.gitignore` yet — create one:

```bash
echo ".env" > .gitignore
```

Also commit `.env.example` without real values so others know what to configure:

```env
AI_GATEWAY_API_KEY=your_vercel_ai_gateway_key_here
AI_GATEWAY_MODEL=openai/gpt-4o-mini
```

---

## Scripts

### `investigate.py` — Generate test cases

Opens the page, runs 4 interaction scenarios (happy path, empty submit, special characters, whitespace only), collects real observations, and generates test cases via AI.

```bash
python investigate.py <url> [output-dir] [count] [complexity]
```

**Arguments:**

| Argument | Description | Default |
|----------|-------------|---------|
| `url` | Page URL to investigate | required |
| `output-dir` | Folder for output files | `./test-cases` |
| `count` | Number of test cases to generate (1–10) | `10` |
| `complexity` | `simple` / `medium` / `e2e` | `medium` |

**Examples:**

```bash
# 10 medium test cases (defaults)
python investigate.py https://www.qa-practice.com/elements/input/simple

# 5 simple test cases into a custom folder
python investigate.py https://example.com/login ./my-cases 5 simple

# 3 full e2e scenarios
python investigate.py https://example.com/checkout ./my-cases 3 e2e
```

**Complexity levels:**

| Level | Steps | When to use |
|-------|-------|-------------|
| `simple` | 2–3 | Quick UI checks: element visibility, correct labels, link redirects |
| `medium` | 4–5 | Standard functional testing: forms, buttons, input validation |
| `e2e` | 6–10+ | Full user flows from page open to final result |

**Output:**

```
test-cases/
├── www_example_com_login_all_testcases.md   ← all test cases in one file
├── TC-001_Submit_button_visible.md
├── TC-002_Empty_field_validation.md
├── TC-003_Valid_login_redirects.md
└── ...
```

---

### `investigate_with_locators.py` — Generate test cases + locator artifacts

Same as `investigate.py` but additionally saves technical artifacts for each test case.

```bash
python investigate_with_locators.py <url> [output-dir] [count] [complexity]
```

Arguments and complexity levels are identical to `investigate.py`.

**Examples:**

```bash
python investigate_with_locators.py https://example.com/form ./test-cases 5 medium

python investigate_with_locators.py https://example.com/checkout ./test-cases 3 e2e
```

**Output per test case:**

| File | For | Contains |
|------|-----|----------|
| `TC-001_<title>.md` | QA engineer | Human-readable test case |
| `TC-001_<title>_locators.yaml` | Automation engineer | All interactive elements: ref, role, name |
| `TC-001_<title>_dom.html` | Developer / automation | Full HTML structure of the page |
| `TC-001_<title>_screenshot.png` | Everyone | Annotated screenshot of the page |

> Test cases themselves never contain technical refs — they are always human-readable.

---

### `regression.py` — Automated regression run

Reads existing `TC-*.md` files, executes steps via browser, and compares the actual page state with the expected result using AI.

```bash
# Run all TC-*.md in ./test-cases/
python regression.py

# Run from a specific folder
python regression.py ./test-cases/checkout

# Run a single test case by ID
python regression.py ./test-cases TC-003
```

**How it works:**

1. Finds all `TC-*.md` files in the specified folder
2. Parses URL, steps, and expected result from each file
3. Opens the page and executes steps via `agent-browser`
4. AI translates each step into a browser command (`click`, `fill`, `check`, etc.)
5. After execution, AI compares the actual page state with the expected result
6. Saves a `regression_report.md` report

**Verdicts:**

| Verdict | Meaning |
|---------|---------|
| ✅ PASS | Actual page state matches the expected result |
| ⚠️ WARNING | Needs manual review — something didn't match or a step couldn't be executed |

> The script intentionally does not set FAIL — it flags uncertain cases as WARNING so a QA engineer makes the final call.

**Output:**

```
test-cases/
└── regression_report.md   ← summary report with a table and details for each WARNING
```

---

### `clean.py` — Clean up the output folder

Deletes all generated files from the `test-cases` folder (or any other folder).

```bash
# Clean ./test-cases/
python clean.py

# Clean a custom folder
python clean.py ./my-folder
```

Deletes files with extensions: `.md`, `.png`, `.txt`, `.yaml`, `.yml`, `.html`, `.htm`, `.json` and all subfolders.

Before deleting, shows a summary and asks for confirmation:

```
Will delete from ./test-cases:
  12 .md files
  12 .yaml files
  12 .html files
  12 .png files

Confirm? (y/n):
```

---

## Full workflow

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO

# 2. Configure .env (one time)
cp .env.example .env
# open .env and paste your AI_GATEWAY_API_KEY

# 3. Generate test cases for a page
python investigate.py https://your-site.com/page ./test-cases 10 medium

# 4. Review and optionally edit the test cases in ./test-cases/

# 5. Run regression after changes on the site
python regression.py ./test-cases

# 6. Check the report
# ./test-cases/regression_report.md

# 7. Clean up before the next run
python clean.py ./test-cases
```

---

## Repository structure

```
explorer-bot/
├── .env                          ← your API keys (never commit this)
├── .env.example                  ← template for other developers
├── .gitignore
├── README.md
├── investigate.py                ← test case generation
├── investigate_with_locators.py  ← test case generation + locator artifacts
├── regression.py                 ← automated regression run
├── clean.py                      ← clean output folder
└── test-cases/                   ← generated files (add to .gitignore if needed)
    ├── TC-001_...md
    ├── TC-002_...md
    └── regression_report.md
```

---

## Troubleshooting

**`agent-browser: command not found`**  
→ Make sure Node.js is installed and run `npm install -g agent-browser` again.

**`Error: AI_GATEWAY_API_KEY not set`**  
→ Check that `.env` exists in the same folder where you run the script and the key is set correctly.

**`HTTP 401` or `HTTP 403` from AI**  
→ The API key is invalid or credits are exhausted. Check your Vercel Dashboard.

**Browser doesn't open**  
→ Install Playwright browsers: `npx playwright install chromium`

**Test cases are generated empty**  
→ Check the model in `.env`. Try `openai/gpt-4o-mini` as the most stable option.

---

## License

MIT
