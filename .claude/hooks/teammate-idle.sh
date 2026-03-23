#!/bin/bash
# teammate-idle.sh — Quality gate for Agent Teams teammates
# Hook event: TeammateIdle
# Exit 0 = OK (no action), Exit 2 = send feedback (stdout → teammate)
#
# Checks:
# 1. Modified Python files — syntax validation
# 2. Modified skill files — YAML frontmatter presence
# 3. Uncommitted debug artifacts (print statements, console.log)

FEEDBACK=""

# Check modified (unstaged) files
MODIFIED=$(git diff --name-only 2>/dev/null)

if [ -z "$MODIFIED" ]; then
    # No changes — teammate may be researching or planning, OK
    exit 0
fi

# Check 1: Python syntax validation
PY_FILES=$(echo "$MODIFIED" | grep '\.py$')
if [ -n "$PY_FILES" ]; then
    for f in $PY_FILES; do
        if [ -f "$f" ]; then
            ERR=$(python -c "import py_compile; py_compile.compile('$f', doraise=True)" 2>&1)
            if [ $? -ne 0 ]; then
                FEEDBACK="${FEEDBACK}Syntax error in $f: $ERR\n"
            fi
        fi
    done
fi

# Check 2: Skill files must have YAML frontmatter
SKILL_FILES=$(echo "$MODIFIED" | grep 'SKILL\.md$')
if [ -n "$SKILL_FILES" ]; then
    for f in $SKILL_FILES; do
        if [ -f "$f" ]; then
            HEAD=$(head -1 "$f")
            if [ "$HEAD" != "---" ]; then
                FEEDBACK="${FEEDBACK}Skill file $f missing YAML frontmatter (must start with ---)\n"
            fi
        fi
    done
fi

# Check 3: Debug artifacts in modified files
DEBUG_HITS=$(echo "$MODIFIED" | xargs grep -ln 'console\.log\|print("DEBUG\|breakpoint()\|import pdb' 2>/dev/null)
if [ -n "$DEBUG_HITS" ]; then
    FEEDBACK="${FEEDBACK}Debug artifacts found in: $DEBUG_HITS — remove before finalizing.\n"
fi

# Verdict
if [ -n "$FEEDBACK" ]; then
    echo -e "Quality gate feedback:\n$FEEDBACK"
    echo "Please fix these issues before marking your task as complete."
    exit 2
fi

exit 0
