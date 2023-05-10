#!/usr/bin/env python3
"""Check code snippets in docs are formatted by black."""
import argparse
import os
import re
import subprocess
import textwrap
from collections.abc import Sequence
from pathlib import Path
from re import Match

import black
from black.mode import Mode, TargetVersion
from black.parsing import InvalidInput

TARGET_VERSIONS = ["py37", "py38", "py39", "py310", "py311"]
SNIPPED_RE = re.compile(
    r"(?P<before>^(?P<indent> *)```\s*python\n)"
    r"(?P<code>.*?)"
    r"(?P<after>^(?P=indent)```\s*$)",
    re.DOTALL | re.MULTILINE,
)

# For some rules, we don't want black to fix the formatting as this would "fix" the
# example.
KNOWN_FORMATTING_VIOLATIONS = [
    "avoidable-escaped-quote",
    "bad-quotes-docstring",
    "bad-quotes-inline-string",
    "bad-quotes-multiline-string",
    "explicit-string-concatenation",
    "line-too-long",
    "missing-trailing-comma",
    "multi-line-implicit-string-concatenation",
    "multiple-statements-on-one-line-colon",
    "multiple-statements-on-one-line-semicolon",
    "prohibited-trailing-comma",
    "trailing-comma-on-bare-tuple",
    "useless-semicolon",
]

# For some docs, black is unable to parse the example code.
KNOWN_PARSE_ERRORS = [
    "blank-line-with-whitespace",
    "missing-newline-at-end-of-file",
    "mixed-spaces-and-tabs",
    "trailing-whitespace",
]

# For some docs we want to ignore that a rule violation is detected.
KNOWN_RULE_VIOLATIONS = []


class CodeBlockError(Exception):
    """A code block parse error."""


def format_str(
    src: str,
    black_mode: black.FileMode,
) -> tuple[str, Sequence[CodeBlockError]]:
    """Format a single docs file string."""
    errors: list[CodeBlockError] = []

    def _snipped_match(match: Match[str]) -> str:
        code = textwrap.dedent(match["code"])
        try:
            code = black.format_str(code, mode=black_mode)
        except InvalidInput as e:
            errors.append(CodeBlockError(e))

        code = textwrap.indent(code, match["indent"])
        return f'{match["before"]}{code}{match["after"]}'

    src = SNIPPED_RE.sub(_snipped_match, src)
    return src, errors


def format_file(
    file: Path,
    black_mode: black.FileMode,
    error_known: bool,
    args: argparse.Namespace,
) -> int:
    """Check the formatting of a single docs file.

    Returns the exit code for the script.
    """
    with file.open() as f:
        contents = f.read()

    if file.parent.name == "rules":
        # Check contents contains "What it does" section
        if "## What it does" not in contents:
            print(f"Docs for `{file.name}` are missing the `What it does` section.")
            return 1

        # Check contents contains "Why is this bad?" section
        if "## Why is this bad?" not in contents:
            print(f"Docs for `{file.name}` are missing the `Why is this bad?` section.")
            return 1

    # Remove everything before the first example
    contents = contents[contents.find("## Example") :]

    # Remove everything after the last example
    contents = contents[: contents.rfind("```")] + "```"

    new_contents, errors = format_str(contents, black_mode)

    if errors and not args.skip_errors and not error_known:
        for error in errors:
            rule_name = file.name.split(".")[0]
            print(f"Docs parse error for `{rule_name}` docs: {error}")

        return 2

    if contents != new_contents:
        rule_name = file.name.split(".")[0]
        print(
            f"Rule `{rule_name}` docs are not formatted. The example section "
            f"should be rewritten to:",
        )

        # Add indentation so that snipped can be copied directly to docs
        for line in new_contents.splitlines():
            output_line = "///"
            if len(line) > 0:
                output_line = f"{output_line} {line}"

            print(output_line)

        print("\n")

        return 1

    return 0


def check_rule(src: str, rule: str, rule_name: str) -> tuple[int, int]:
    """Check rule violation present."""
    first_snippet = True  # Example is first snippet and violation should be present
    missing_violation = 0
    unexpected_violation = 0

    def _snipped_match(match: Match[str]) -> None:
        nonlocal first_snippet
        nonlocal missing_violation
        nonlocal unexpected_violation

        output = subprocess.run(
            [
                "ruff",
                "check",
                "-",
                "--stdin-filename",
                f"test_{rule}.{'pyi' if 'PYI' in rule else 'py'}",
                f"--select={rule}",
                "--format=json",
            ],
            input=textwrap.dedent(match["code"]),
            capture_output=True,
            timeout=2,
            text=True,
        )

        if first_snippet:
            if rule not in output.stdout:
                missing_violation += 1
                print_violation_error(match["code"], violation_type="Expected")
        else:
            if rule in output.stdout:
                unexpected_violation += 1
                print_violation_error(match["code"], violation_type="Unexpected")

        first_snippet = False

    def print_violation_error(code: str, violation_type: str) -> None:
        """Print violation error."""
        nonlocal rule_name
        print(
            f"{violation_type} violation {rule} ({rule_name}) was"
            f" {'' if violation_type == 'Unexpected' else 'not '}found in the following"
            " code snippet.",
        )

        print("/// ```python")
        for line in code.splitlines():
            output_line = "///"
            if len(line) > 0:
                output_line = f"{output_line} {line}"

            print(output_line)

        print("/// ```")
        print("\n")

    SNIPPED_RE.sub(_snipped_match, src)

    return missing_violation, unexpected_violation


def check_ruff_rules(docs: list[Path]) -> tuple[int, int]:
    """Check the expected rule violations are present in the docs.

    Returns the number of unexpected and missing violations.
    """
    unexpected_violations, missing_violations = 0, 0
    for file in docs:
        rule_name = file.name.split(".")[0]
        if rule_name in KNOWN_RULE_VIOLATIONS:
            continue

        with file.open() as f:
            contents = f.read()

        first_line = contents.splitlines()[0]

        # Remove everything before the first example
        contents = contents[contents.find("## Example") :]

        # Remove everything after the last example
        contents = contents[: contents.rfind("```")] + "```"

        rule = None
        if first_line.find("(") != -1 and first_line.find(")") != -1:
            first_line = first_line[first_line.find("(") + 1 :]
            rule = first_line[: first_line.find(")")]

        rule_name = file.name.split(".")[0]

        if rule is not None:
            rule_unexpected_violations, rule_missing_violations = check_rule(
                contents,
                rule,
                rule_name,
            )
            unexpected_violations += rule_unexpected_violations
            missing_violations += rule_missing_violations

    return unexpected_violations, missing_violations


def main(argv: Sequence[str] | None = None) -> int:
    """Check code snippets in docs are formatted by black."""
    parser = argparse.ArgumentParser(
        description="Check code snippets in docs are formatted by black.",
    )
    parser.add_argument("--skip-errors", action="store_true")
    parser.add_argument("--generate-docs", action="store_true")
    args = parser.parse_args(argv)

    if args.generate_docs:
        # Generate docs
        from generate_mkdocs import main as generate_docs

        generate_docs()

    # Get static docs
    static_docs = []
    for file in os.listdir("docs"):
        if file.endswith(".md"):
            static_docs.append(Path("docs") / file)

    # Check rules generated
    if not Path("docs/rules").exists():
        print("Please generate rules first.")
        return 1

    # Get generated rules
    generated_docs = []
    for file in os.listdir("docs/rules"):
        if file.endswith(".md"):
            generated_docs.append(Path("docs/rules") / file)

    if len(generated_docs) == 0:
        print("Please generate rules first.")
        return 1

    docs = [*static_docs, *generated_docs]
    black_mode = Mode(
        target_versions={TargetVersion[val.upper()] for val in TARGET_VERSIONS},
    )

    # Check known formatting violations and parse errors are sorted alphabetically and
    # have no duplicates. This will reduce the diff when adding new violations

    for known_list, file_string in [
        (KNOWN_FORMATTING_VIOLATIONS, "formatting violations"),
        (KNOWN_PARSE_ERRORS, "parse errors"),
        (KNOWN_RULE_VIOLATIONS, "rule violations"),
    ]:
        if known_list != sorted(known_list):
            print(
                f"Known {file_string} is not sorted alphabetically. Please sort and "
                f"re-run.",
            )
            return 1

        duplicates = list({x for x in known_list if known_list.count(x) > 1})
        if len(duplicates) > 0:
            print(f"Known {file_string} has duplicates:")
            print("\n".join([f"  - {x}" for x in duplicates]))
            print("Please remove them and re-run.")
            return 1

    violations = 0
    errors = 0
    for file in docs:
        rule_name = file.name.split(".")[0]
        if rule_name in KNOWN_FORMATTING_VIOLATIONS:
            continue

        error_known = rule_name in KNOWN_PARSE_ERRORS

        result = format_file(file, black_mode, error_known, args)
        if result == 1:
            violations += 1
        elif result == 2 and not error_known:
            errors += 1

    unexpected_violations, missing_violations = check_ruff_rules(docs)

    if violations > 0:
        print(f"Formatting violations identified: {violations}")

    if errors > 0:
        print(f"New code block parse errors identified: {errors}")

    if unexpected_violations > 0:
        print(f"Unexpected rule violations identified: {unexpected_violations}")

    if missing_violations > 0:
        print(f"Missing rule violations identified: {missing_violations}")

    if sum([violations, errors, unexpected_violations, missing_violations]) > 0:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
