---
name: generate-loop
description: >-
  Generate an agentic loop that can be run autonomously without user interation. Script(s) are created that invoke IBM Bob Shell which is the 'bob' command line interface.
  Use this whenever the user mentions loop or loops generation.
metadata:
  enabled: true
---

Agentic loops run long taking tasks autonomously by leveraging well defined deterministic scripts to trigger the AI-based development tool Bob for non-deterministic tasks.

Scripts make the loops more reliable. If something can be done via script, prefer it versus AI. Generate all scripts that are necessary.

The user input contains two pieces of information:
1. WHAT needs to be done
2. DONE - definition of when the loop is done

Note that that the loop can only be triggered manually by invoking the scripts (there is no scheduler).

Plan carefully how to break down the `WHAT` into multiple steps/iterations! Define in the script when the goal is reached (`DONE`)!

Create the following directories and files:
- [project root directory]
  - `loop` directory
    - [loop name].sh
    - [iteration name].sh
    - [prompt name].md
    - README.md instructions how to run the loop(s)

The scripts need to work on MacOS, Windows and Linux.

If the repo has no .git, initialize it. Before changing anything create a git branch. After every iteration changes need to be committed to that branch.

Never change or add files to the `.bob` directory.


# Setup of Bob Shell

Bob Shell setup is handled by a platform-agnostic setup script included in this skill's assets.
Run these scripts first in the loop scripts (do not copy the files).

| Platform        | Script                                                      | How to run                                          |
|-----------------|-------------------------------------------------------------|-----------------------------------------------------|
| macOS / Linux   | `.bob/skills/generate-loop/scripts/setup.sh`                | `bash .bob/skills/generate-loop/scripts/setup.sh --env-file .env` |
| Windows (PS)    | `.bob/skills/generate-loop/scripts/setup.ps1`               | `& ".bob/skills/generate-loop/scripts/setup.ps1"`   |

The script will:
1. Load `.env` from the working directory (copy from `.bob/skills/generate-loop/assets/.env-template`).
2. Validate that the required value is present — exit with a clear message if missing:
   ```text
   BOBSHELL_API_KEY="xxx"   # get from https://bob.ibm.com/admin/apikeys
   ```
   `GIT_USER_EMAIL` and `GIT_USER_NAME` are read automatically from `git config` and do not need to be set.
3. Detect the OS and install Bob Shell if missing or at the wrong version (required: `1.0.6`).
4. Confirm a successful install with `bob --version`.

Always include the following README snippet in the generated `loops/README.md`:

```markdown
## Prerequisites

1. Copy the environment template and fill in your values (get it from https://bob.ibm.com/admin/apikeys):
   ```sh
   cp .bob/skills/generate-loop/assets/.env-template .env
   ```

2. Edit `.env` and set `BOBSHELL_API_KEY`.

3. Start the loop:
   - macOS / Linux: `bash loops/loop.sh`
   - Windows:       `.\loops\loop.ps1`
```

`loop.sh` and `loop.ps1` need to run `setup.sh` or `setup.ps1` first.

> **Important**: Always pass `--env-file .env` explicitly when calling `setup.sh` from a generated script:
> ```bash
> source "$REPO_ROOT/.bob/skills/generate-loop/scripts/setup.sh" --env-file "$REPO_ROOT/.env"
> ```
> `setup.sh` runs with `set -euo pipefail`. The `-u` flag causes an "unbound variable" crash on line
> `ENV_FILE="${1:-.env}"` when no argument is supplied, because `$1` is unset at that point.
> Passing `--env-file .env` ensures `$1` is always defined and the default substitution is never reached.

## Bash compatibility guard

`setup.sh` uses bash-only syntax (`[[ ]]`, `set -o pipefail`, `BASH_SOURCE`, etc.).
If a user runs `sh loop.sh` instead of `bash loop.sh`, the script will fail with an
"unbound variable" or syntax error before setup even starts.

**Every generated `loop.sh` and `iteration.sh` must include this guard as the very
first executable lines after the shebang and comments:**

```bash
#!/usr/bin/env bash
# ...comments...

# Re-exec under bash if invoked via plain sh (e.g. "sh loop/loop.sh")
if [ -z "${BASH_VERSION:-}" ]; then
    exec bash "$0" "$@"
fi

set -euo pipefail
```

The guard uses only POSIX-compatible `[ ]` syntax so that `sh` can parse and execute
it, then immediately re-execs the script under `bash` before any bash-only code runs.
This makes `sh loop/loop.sh`, `bash loop/loop.sh`, and `./loop/loop.sh` all work
correctly.


# Token & BobCoin Usage

When `bob` is run with `--output-format=stream-json`, the **last line** of stdout is a JSON object whose `.usage` field contains token counts and BobCoin spend. Always capture the full output into a variable, print it, then extract and display the usage summary at the end of each iteration:

```bash
BOB_OUTPUT=$(cat "$PROMPT_FILE" | bob \
    --auth-method api-key \
    --output-format=stream-json)
echo "$BOB_OUTPUT"

# Display usage summary
LAST_LINE=$(echo "$BOB_OUTPUT" | tail -n 1)
INPUT_TOKENS=$(echo "$LAST_LINE" | jq -r '.usage.input_tokens // "n/a"')
OUTPUT_TOKENS=$(echo "$LAST_LINE" | jq -r '.usage.output_tokens // "n/a"')
BOB_COINS=$(echo "$LAST_LINE"   | jq -r '.usage.bob_coins     // "n/a"')
echo ""
echo "📊 Iteration $ITERATION usage — input tokens: $INPUT_TOKENS | output tokens: $OUTPUT_TOKENS | bobcoins: $BOB_COINS"
```

**Rules:**
- Every generated `iteration.sh` **must** follow this pattern — never pipe `bob` output directly to the terminal without capturing it first.
- Use `// "n/a"` fallbacks in `jq` so the script does not fail if a field is absent in older Bob Shell versions.


# Bob Usage

Critical: You must invoke bob with the following parameters!

```bash
BOB_OUTPUT=$(cat "$PROMPT_FILE" | bob \
    --auth-method api-key \
    --accept-license \
    --sandbox \
    --yolo \
    --allowed-tools read_file,write_todos,write_to_file,run_shell_command \
    --output-format=stream-json)
```

# Example Loop Implementation

The following code runs a loop to implement features of an application. This is just an example. Your task is to create similar assets for the `WHAT` and `DONE` as defined by the user.

## loop.sh:

```bash
#!/bin/bash

MAX_ITERATIONS=5
ITERATION=0
APPLICATION_DIR=$(pwd)
PLAN_FILE="$APPLICATION_DIR/ralph/IMPLEMENTATION_PLAN.md"

echo "--- Starting Ralph Wiggum Loop ---"

while true; do
    if [ -f "$PLAN_FILE" ]; then
        if ! grep -q "\- \[ \]" "$PLAN_FILE"; then
            echo "✅ Success! No unchecked tasks found in $PLAN_FILE."
            echo "Ralph says: 'I finished helping!'"
            break
        fi
    fi

    # 2. MAX ITERATION CHECK
    if [ $MAX_ITERATIONS -gt 0 ] && [ $ITERATION -ge $MAX_ITERATIONS ]; then
        echo "🛑 Reached max iterations: $MAX_ITERATIONS"
        break
    fi

    echo "--- Running Iteration $ITERATION ---"

    # 3. CALL THE ITERATION SCRIPT
    /workspace/ralph/iteration.sh "$ITERATION"

    ITERATION=$((ITERATION + 1))
done
```

## iteration.sh:

```bash
#!/bin/bash

APPLICATION_DIR=$(pwd)
ITERATION=$1
PROMPT_FILE="$APPLICATION_DIR/../ralph/PROMPT.md"
git config --global --add safe.directory /workspace/application
git config --global --add safe.directory /workspace

# ── Ensure a git repo exists ──────────────────────────────────────────────────
if [ ! -d "$APPLICATION_DIR/.git" ]; then
    echo "No .git found — initialising repository"
    git -C "$APPLICATION_DIR" init
    git -C "$APPLICATION_DIR" add .
    git -C "$APPLICATION_DIR" commit -m "Initial commit" --allow-empty
fi

# 1. DETERMINE ITERATION NUMBER
if [ -z "$ITERATION" ]; then
    LAST_COMMIT=$(git log --all --grep="Ralph Wiggum Iteration" --format="%s" -n 1 2>/dev/null)
    
    if [ -n "$LAST_COMMIT" ]; then
        LAST_ITERATION=$(echo "$LAST_COMMIT" | grep -oE '[0-9]+$')
        if [ -n "$LAST_ITERATION" ]; then
            ITERATION=$((LAST_ITERATION + 1))
            echo "Found last iteration: $LAST_ITERATION, using iteration: $ITERATION"
        else
            ITERATION=1
            echo "No valid iteration number found in git history, starting from: $ITERATION"
        fi
    else
        ITERATION=1
        echo "No previous Ralph Wiggum commits found, starting from: $ITERATION"
    fi
else
    echo "Using provided iteration: $ITERATION"
fi

# 2. PROMPT CHECK
if [ ! -n "${PROMPT_FILE+x}" ]; then
    echo "Error: $PROMPT_FILE not found at $PROMPT_FILE"
    exit 1
fi

# 3. CORE WORK
BOB_OUTPUT=$(cat "$PROMPT_FILE" | bob \
    --auth-method api-key \
    --accept-license \
    --sandbox \
    --yolo \
    --allowed-tools read_file,write_todos,write_to_file,run_shell_command \
    --output-format=stream-json)
echo "$BOB_OUTPUT"

# 3b. USAGE SUMMARY
LAST_LINE=$(echo "$BOB_OUTPUT" | tail -n 1)
INPUT_TOKENS=$(echo "$LAST_LINE" | jq -r '.usage.input_tokens // "n/a"')
OUTPUT_TOKENS=$(echo "$LAST_LINE" | jq -r '.usage.output_tokens // "n/a"')
BOB_COINS=$(echo "$LAST_LINE"   | jq -r '.usage.bob_coins     // "n/a"')
echo ""
echo "📊 Iteration $ITERATION usage — input tokens: $INPUT_TOKENS | output tokens: $OUTPUT_TOKENS | bobcoins: $BOB_COINS"

# 4. COMMIT
git config --global --add safe.directory /workspace/application
git config --global --add safe.directory /workspace
git add .
git commit -m "Ralph Wiggum Iteration $ITERATION" --allow-empty
```

## PROMPT.md:

```markdown
**Crucial**: Never ask any questions!

You are an expert software engineer named Ralph. Your goal is to implement the functionality described in the `specs/` folder by following the `IMPLEMENTATION_PLAN.md`.

## Instructions
1. **Orient**: 
   - Read the files in `@ralph/specs/` to understand what needs to be built.
   - If necessary, read the code in the current directory
   - If necessary, check the git log for previous work
2. **Plan**: 
   - Read `@ralph/IMPLEMENTATION_PLAN.md` to see what tasks are remaining.
   - Read `@ralph/PROGRESS.md` to see what has been done previously.
3. **Select**: 
   - Pick the highest priority "Todo" item from the plan. 
   - Only pick one of the features.
   - When choosing the next task, prioritize in this order. Fail fast on risky work. Save easy wins for later:
     1. Architectural decisions and core abstractions
     2. Integration points between modules
     3. Unknown unknowns and spike work
     4. Standard features and implementation
     5. Polish, cleanup, and quick wins
4. **Act**:
   - Write the code to implement that single task.
   - Run tests to verify your code works.
   - **Crucially**: Update `@ralph/IMPLEMENTATION_PLAN.md` to mark the task as "Done".
   - Append your progress to `@ralph/PROGRESS.md`. Keep entries concise. Sacrifice grammar for the sake of concision. This file helps future iterations skip exploration:
     - Tasks completed in this session
     - Decisions made and why
     - Blockers encountered
     - Files changed
5. **Stop**: Do not try to do everything at once. Do one thing well, then exit.

## Constraints
- If a file doesn't exist, create it.
- If tests fail, fix the code before marking the task done.
```

## IMPLEMENTATION_PLAN.md example:

```markdown
# Implementation Plan

## Feature: Hello Ralph Generator (specs/hello_ralph.md)
- [ ] Create `ralph_sayer.py` with the predefined list of quotes.
- [ ] Implement random selection logic in `ralph_sayer.py`.
- [ ] Create `test_ralph_sayer.py` to verify the script runs.
- [ ] Run tests and verify "Hello Ralph" feature works.

## Feature: Ralph Math Helper (specs/ralph_math.md)
- [ ] Create `ralph_math.py` skeleton that accepts command line arguments.
- [ ] Implement the addition logic and the "Result > 10" check.
- [ ] Implement the error handling for non-number inputs.
- [ ] Create `test_ralph_math.py` to check cases (e.g. 2+2, 5+6, and invalid input).
- [ ] Run tests and verify "Ralph Math" feature works.
```

## specs/ralph_math.md example:

```mardown
# Spec: Ralph's Math Helper

## Overview
We need a utility script that helps Ralph with his homework. Ralph is not very good at math, but he tries his best.

## Requirements
1. **Script Name**: The script should be named `ralph_math.py`.
2. **Input**: The script must accept two integer arguments from the command line (e.g., `python3 ralph_math.py 5 3`).
3. **Logic**:
   - The script should calculate the sum of the two numbers.
   - If the sum is greater than 10, it is "too hard" for Ralph.
4. **Output**:
   - If sum <= 10: Print the result followed by "I calculate good!" (e.g., `8 ... I calculate good!`).
   - If sum > 10: Print "That is unpossible!"
5. **Error Handling**: If the user provides non-numbers, print "My cat's name is Mittens."
```

## specs/hello_ralph.md example:

```markdow
# Spec: Hello Ralph Generator

## Overview
We need a simple command-line script that greets the user with a quote from Ralph Wiggum.

## Requirements
1. **Script Name**: The script should be named `ralph_sayer.py`.
2. **Behavior**: When run, it should print a random quote from a predefined list of Ralph Wiggum quotes.
3. **Quotes List**:
   - "I'm helping!"
   - "Me fail English? That's unpossible!"
   - "My cat's breath smells like cat food."
4. **Execution**: The script must be executable via `python3 ralph_sayer.py`.
```
