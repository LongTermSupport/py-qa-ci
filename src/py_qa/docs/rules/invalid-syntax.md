# invalid-syntax

Printed by the `ruff` lane. It is not a rule in Ruff's catalogue, so `ruff rule invalid-syntax`
does not know it, and no setting selects or ignores it.

## What it flags

Python that Ruff cannot accept as Python, in one of three ways:

- **A parse error**: the file does not follow Python's grammar (`def broken(:`, an unclosed
  bracket, a stray indent). Ruff cannot build the file's syntax tree, so the rules that read it,
  most of them (an unused import, an undefined name, every security rule), are not checked in
  that file; only the few that read its tokens and lines are.
- **A syntax error the compiler would raise**: the grammar is followed, but Python rejects the
  code before it runs (`nonlocal` at module level, a duplicate parameter name, a second `**`
  pattern in one `case`). The rest of the file is checked as usual, so other findings appear
  beside it.
- **Syntax newer than the target version**: valid Python, but not on the oldest Python the
  project supports (a `match` statement with a target of Python 3.8), read from Ruff's
  `target-version` or the project's `requires-python`.

The message after the code says what Ruff could not accept, and the line and column say where.

## Why

Code that is not valid Python fails when it is imported, not when it is reviewed, and a file with
a parse error is invisible to every other check: Ruff, mypy and Pylint each skip or stop on it,
so a defence that should have fired there stays silent. The file has to parse before any finding
about it means anything.

## How to fix correctly

Correct the code at the line and column given, until the file compiles: `python -m py_compile <file>` reports the same fault. Then run `py-qa run` again, because the findings the parse error
hid are reported only once the file parses. If the syntax is valid on a newer Python than the
project's lowest supported version, the code needs that version: raise `requires-python` (and
Ruff's `target-version`) deliberately, or write it in the older form. A file that is not meant to
be Python at all, such as a template with a `.py` name, is renamed or kept out of the lane's
paths, not suppressed.
