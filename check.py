#!/usr/bin/env python3
"""
harness.py: Lab 4 marking script.

    python harness.py path/to/student_repo
    python harness.py --all path/to/all_submissions --out results/

Runs 14 checks worth 5.5 marks. No network. No reading anyone's code.

It works on a temporary copy of the repo, and it overwrites the copy's
stub_client.py with its own, so a student who edited the stub gains
nothing. The student's own samples/*.json are kept - that is the point
of the design.

Requires the marker's Python to have: pydantic, python-dotenv, openai.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFERENCE = HERE / "reference_files"     # holds client.py and stub_client.py
SELF_CHECK = not REFERENCE.exists()      # student copy: no reference dir shipped


def ref(name: str, repo: Path) -> Path:
    """The authoritative copy of a supplied file, or the repo's own in self-check."""
    return (repo / name) if SELF_CHECK else (REFERENCE / name)

TIMEOUT = 45

REQUIRED_FILES = [
    "main.py",
    "client.py",
    "stub_client.py",
    "check.py",
    "SPEC.md",
    "DECISIONS.md",
    "QUESTION.md",
    ".gitignore",
    "requirements.txt",
    ".env.example",
    "samples/valid_response.json",
    "samples/invalid_response.json",
]

SPEC_HEADINGS = [
    "# What it does",
    "# Inputs",
    "# Outputs",
    "# Failure cases",
    "# Acceptance checks",
    "# Out of scope",
]

# mode -> (expected last stdout line, expected exit code)
BEHAVIOUR = {
    "ok":        ("ok", 0),
    "fenced":    ("ok", 0),
    "preamble":  ("ok", 0),
    "malformed": ("invalid_output", 1),
    "badshape":  ("invalid_output", 1),
    "empty":     ("invalid_output", 1),
    "refused":   ("refused", 1),
    "error":     ("error", 1),
}

TOPIC = "photosynthesis"


# --------------------------------------------------------------------------

@dataclass
class Check:
    group: str
    name: str
    marks: float
    passed: bool = False
    note: str = ""


@dataclass
class Result:
    repo: str
    checks: list[Check] = field(default_factory=list)

    @property
    def awarded(self) -> float:
        return round(sum(c.marks for c in self.checks if c.passed), 2)

    @property
    def total(self) -> float:
        return round(sum(c.marks for c in self.checks), 2)


def git(repo: Path, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=20,
        )
        return out.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return ""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_app(workdir: Path, topic: str, mode: str) -> tuple[str, int, str]:
    """Run main.py once. Returns (last stdout line, exit code, stderr tail)."""
    env = dict(os.environ)
    env["LLM_API_KEY"] = "not-needed"
    env["LLM_BASE_URL"] = "local://stub"
    env["LLM_MODEL"] = f"stub:{mode}"
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("LLM_PROVIDER", None)

    call_log = workdir / ".stub_calls.log"
    call_log.unlink(missing_ok=True)

    try:
        proc = subprocess.run(
            [sys.executable, "main.py", topic],
            cwd=str(workdir), env=env, capture_output=True,
            text=True, timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return ("<timeout>", -1, f"no output within {TIMEOUT}s")

    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    last = lines[-1] if lines else "<no output>"
    return (last, proc.returncode, proc.stderr.strip()[-300:])


# --------------------------------------------------------------------------

def check_repo(repo: Path) -> Result:
    res = Result(repo=repo.name)
    add = res.checks.append

    # ---- Group A: repo and contract (1.5) --------------------------------
    missing = [f for f in REQUIRED_FILES if not (repo / f).exists()]
    add(Check("A", "Required files present", 0.3, not missing,
              "" if not missing else "missing: " + ", ".join(missing)))

    student_client = repo / "client.py"
    same = student_client.exists() and (
        SELF_CHECK or sha256(student_client) == sha256(ref("client.py", repo))
    )
    add(Check("A", "client.py unmodified", 0.3, same,
              "" if same else "client.py differs from the supplied file"))

    ignored = (repo / ".gitignore").exists() and ".env" in (repo / ".gitignore").read_text()
    history = git(repo, "log", "--all", "--name-only", "--pretty=format:")
    committed = any(ln.strip() == ".env" for ln in history.splitlines())
    add(Check("A", ".env ignored and never committed", 0.3,
              ignored and not committed,
              "" if ignored and not committed else
              ("'.env' not in .gitignore; " if not ignored else "") +
              (".env appears in git history" if committed else "")))

    spec_text = (repo / "SPEC.md").read_text(encoding="utf-8", errors="ignore") \
        if (repo / "SPEC.md").exists() else ""
    spec_lines = [ln.strip() for ln in spec_text.splitlines()]
    absent = [h for h in SPEC_HEADINGS if h not in spec_lines]
    add(Check("A", "SPEC.md has the six headings", 0.3, not absent,
              "" if not absent else "missing headings: " + ", ".join(absent)))

    commits = git(repo, "rev-list", "--count", "HEAD")
    n_commits = int(commits) if commits.isdigit() else 0
    tagged = "lab-4-submission" in git(repo, "tag", "-l", "lab-4-submission")
    git_ok = n_commits >= 5 and tagged
    add(Check("A", "Git: >=5 commits and the lab-4-submission tag",
              0.3, git_ok,
              "" if git_ok else
              f"commits={n_commits}, tag={'yes' if tagged else 'no'}"))

    # ---- Behavioural checks on a temp copy -------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "repo"
        shutil.copytree(repo, work, ignore=shutil.ignore_patterns(".git"))
        if not SELF_CHECK:
            shutil.copy2(REFERENCE / "stub_client.py", work / "stub_client.py")
            shutil.copy2(REFERENCE / "client.py", work / "client.py")
        (work / ".env").unlink(missing_ok=True)

        groups = {
            "B": (["ok", "fenced", "preamble"], 1.0),
            "C": (["malformed", "badshape", "empty"], 1.5),
            "D": (["refused", "error"], 1.0),
        }
        for g, (modes, marks) in groups.items():
            per = round(marks / len(modes), 3)
            for mode in modes:
                want_line, want_code = BEHAVIOUR[mode]
                line, code, err = run_app(work, TOPIC, mode)
                ok = (line == want_line) and (code == want_code)
                add(Check(g, f"stub:{mode} -> {want_line} (exit {want_code})",
                          per, ok,
                          "" if ok else f"got {line!r} exit {code}"
                          + (f"; stderr: {err.splitlines()[-1]}" if err else "")))

        # ---- Group E: the input gate (0.5) -------------------------------
        line, code, err = run_app(work, "", "ok")
        no_call = not (work / ".stub_calls.log").exists()
        gate_ok = (code == 2) and no_call
        add(Check("E", 'empty topic -> exit 2, no model call', 0.5, gate_ok,
                  "" if gate_ok else
                  f"exit {code}; model was {'not ' if no_call else ''}called"))

    return res


# --------------------------------------------------------------------------

def render(res: Result) -> str:
    out = [f"# Lab 4: {res.repo}", "",
           f"**Harness: {res.awarded} / {res.total}**", "",
           "| | Check | Marks | Result | Note |",
           "|---|---|--:|:-:|---|"]
    for c in res.checks:
        out.append(f"| {c.group} | {c.name} | {c.marks} | "
                   f"{'PASS' if c.passed else 'FAIL'} | {c.note} |")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default=".")
    ap.add_argument("--all", action="store_true",
                    help="treat path as a directory of student repos")
    ap.add_argument("--out", default="results")
    args = ap.parse_args()

    root = Path(args.path).resolve()
    repos = sorted(p for p in root.iterdir() if p.is_dir()) if args.all else [root]

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    summary = []

    if SELF_CHECK:
        print("[self-check mode] client.py and stub_client.py are taken as-is.\n"
              "The marking run uses the supplied originals.\n")

    for repo in repos:
        res = check_repo(repo)
        print(render(res))
        print()
        (outdir / f"{res.repo}.md").write_text(render(res), encoding="utf-8")
        summary.append({"repo": res.repo, "awarded": res.awarded,
                        "total": res.total,
                        "checks": [c.__dict__ for c in res.checks]})

    (outdir / "summary.json").write_text(json.dumps(summary, indent=2),
                                         encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
