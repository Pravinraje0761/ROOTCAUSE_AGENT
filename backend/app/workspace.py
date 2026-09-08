"""
Workspace connection & real-codebase analysis for RootCause AI.

Allows an operator to connect either:
  - a GitHub repository URL  -> cloned locally (shallow) into backend/workspaces/<id>
  - a local filesystem path   -> referenced directly in place

Once connected, the agent can analyze the ACTUAL codebase: git history,
file structure, dependency manifests, recent risky changes, and generate
evidence-backed findings about where failures are most likely to originate.
"""
import os
import re
import uuid
import shutil
import subprocess
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

WORKSPACES_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "workspaces"
WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)

# Files that likely indicate failure-prone surfaces in a codebase
DEPENDENCY_MANIFESTS = ["package.json", "requirements.txt", "pyproject.toml", "Pipfile",
                        "go.mod", "Cargo.toml", "pom.xml", "build.gradle", "Gemfile",
                        "composer.json", "package-lock.json", "yarn.lock"]
CONFIG_FILES = ["docker-compose.yml", "docker-compose.yaml", "Dockerfile", ".env.example",
                "config.yaml", "config.yml", "config.json", "config.toml", "application.yml",
                "application.properties", "nginx.conf", ".github/workflows"]
# File extensions that are 'live' application code (as opposed to docs / lockfiles)
CODE_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb", ".php",
             ".c", ".cpp", ".h", ".cs", ".scala", ".swift", ".kt", ".sh", ".tf", ".yaml", ".yml", ".json"}

ALLOWED_LOCAL_ROOTS = []  # empty = no local-path restriction (local demo)


def _sanitize_repo_name(url: str) -> str:
    """Extract a safe directory name from a GitHub URL."""
    name = url.rstrip("/").split("/")[-1]
    name = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
    return name or "repo"


def _run_git(args: List[str], cwd: Optional[str] = None, timeout: int = 120) -> Tuple[int, str, str]:
    try:
        proc = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"git command timed out after {timeout}s"
    except FileNotFoundError:
        return -1, "", "git executable not found on this system"
    except Exception as e:
        return -1, "", str(e)


def _is_github_url(url: str) -> bool:
    url = (url or "").strip()
    return url.startswith("https://github.com/") or url.startswith("http://github.com/") or url.startswith("git@github.com:")


def connect_workspace(source: str, url: str = "", path: str = "") -> Dict[str, Any]:
    """Connect a workspace from a GitHub URL or a local path.

    Returns a dict with workspace metadata (id, name, root, git info) on success,
    or raises ValueError describing the problem.
    """
    source = (source or "").lower().strip()

    if source == "github":
        if not _is_github_url(url):
            raise ValueError("Invalid GitHub URL. Must be a github.com repository URL (https://github.com/owner/repo).")
        return _connect_github(url)

    elif source == "local":
        if not path:
            raise ValueError("A local path is required.")
        return _connect_local(path)

    raise ValueError("source must be 'github' or 'local'")


def _connect_github(url: str) -> Dict[str, Any]:
    ws_id = f"gh-{uuid.uuid4().hex[:8]}"
    clone_dir = WORKSPACES_DIR / ws_id
    clone_dir.mkdir(parents=True, exist_ok=True)

    try:
        code, out, err = _run_git(["clone", "--depth", "1", url, "."], cwd=str(clone_dir))
        if code != 0:
            shutil.rmtree(clone_dir, ignore_errors=True)
            raise ValueError(f"Git clone failed: {err.strip()[:500]}")
    except Exception as e:
        if isinstance(e, ValueError):
            raise e
        raise ValueError(f"An error occurred while cloning: {e}")

    name = _sanitize_repo_name(url)
    return _analyze_gh_metadata(ws_id, clone_dir, name, url)


def _analyze_gh_metadata(ws_id: str, root: Path, name: str, url: str) -> Dict[str, Any]:
    branch = ""
    code, out, _ = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=str(root))
    if code == 0:
        branch = out.strip()
    return {
        "id": ws_id,
        "source": "github",
        "name": name,
        "url": url,
        "root": str(root),
        "branch": branch,
        "connected_at": datetime.utcnow().isoformat(),
    }


def _connect_local(path: str) -> Dict[str, Any]:
    p = Path(path).expanduser()
    if not p.exists() or not p.is_dir():
        raise ValueError(f"Local path does not exist or is not a directory: {path}")
    if not os.access(str(p), os.R_OK):
        raise ValueError(f"Local path is not readable: {path}")

    return {
        "id": f"local-{uuid.uuid4().hex[:8]}",
        "source": "local",
        "name": p.name or "workspace",
        "url": "",
        "root": str(p.resolve()),
        "branch": "",
        "connected_at": datetime.utcnow().isoformat(),
    }


def get_repo_metadata(root: str) -> Dict[str, Any]:
    """Extract basic metadata about a connected repo (git + top-level stats)."""
    root = Path(root)
    is_git = (root / ".git").exists() or (root / ".git").is_file()

    metadata = {
        "is_git_repo": is_git,
        "branch": "",
        "recent_commits": [],
        "total_commits": 0,
        "languages": {},
        "file_count": 0,
        "code_file_count": 0,
        "manifests": [],
        "config_files": [],
        "top_dirs": [],
        "size_bytes": 0,
        "readme": "",
    }

    if is_git:
        code, out, _ = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=str(root))
        if code == 0:
            metadata["branch"] = out.strip()

        code, out, _ = _run_git(["rev-list", "--count", "HEAD"], cwd=str(root))
        if code == 0 and out.strip().isdigit():
            metadata["total_commits"] = int(out.strip())

        code, out, _ = _run_git(
            ["log", "-20", "--pretty=format:%h%x09%an%x09%ad%x09%s", "--date=short"], cwd=str(root)
        )
        if code == 0:
            for line in out.splitlines():
                parts = line.split("\t")
                if len(parts) >= 4:
                    metadata["recent_commits"].append({
                        "hash": parts[0], "author": parts[1], "date": parts[2], "message": "\t".join(parts[3:])
                    })

    # Walk the tree, counting files, languages, manifests, and top directories.
    lang_count: Dict[str, int] = {}
    dir_count: Dict[str, int] = {}
    total_size = 0

    ignore_dirs = {".git", "node_modules", "dist", "build", "__pycache__", ".venv", "venv",
                   ".idea", ".vscode", "target", "vendor", ".next", "coverage", ".cache"}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs]
        rel = os.path.relpath(dirpath, root)
        if rel != ".":
            top = rel.split(os.sep)[0]
            dir_count[top] = dir_count.get(top, 0) + len(filenames)
        for fname in filenames:
            total_size += os.path.getsize(os.path.join(dirpath, fname))
            ext = os.path.splitext(fname)[1].lower()
            if ext in CODE_EXTS:
                metadata["code_file_count"] += 1
                lang_count[ext.lstrip(".")] = lang_count.get(ext.lstrip("."), 0) + 1
            if fname in DEPENDENCY_MANIFESTS:
                metadata["manifests"].append(os.path.relpath(os.path.join(dirpath, fname), root))
            if fname in CONFIG_FILES:
                metadata["config_files"].append(os.path.relpath(os.path.join(dirpath, fname), root))
            metadata["file_count"] += 1

    metadata["size_bytes"] = total_size
    metadata["languages"] = dict(sorted(lang_count.items(), key=lambda x: -x[1])[:8])
    metadata["top_dirs"] = [d for d, _ in sorted(dir_count.items(), key=lambda x: -x[1])[:12]]

    # Grab README if present
    for readme in ["README.md", "readme.md", "README.rst", "README"]:
        rp = root / readme
        if rp.exists():
            try:
                metadata["readme"] = rp.read_text(encoding="utf-8", errors="replace")[:4000]
            except Exception:
                pass
            break

    return metadata


def scan_dependency_risks(root: str) -> List[Dict[str, Any]]:
    """Scan dependency manifests and pin a handful of concrete risk findings."""
    root = Path(root)
    findings: List[Dict[str, Any]] = []
    seen = set()

    def _add(finding: Dict[str, Any]):
        key = finding["file"] + "|" + finding["title"]
        if key not in seen:
            seen.add(key)
            findings.append(finding)

    for manifest in DEPENDENCY_MANIFESTS:
        for local_path in root.rglob(manifest):
            if any(part in {"node_modules", ".git", "dist", "build", "__pycache__", ".venv", "venv", "target", "vendor"} for part in local_path.parts):
                continue
            rel = os.path.relpath(str(local_path), root).replace("\\", "/")
            try:
                content = local_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            if manifest in ("requirements.txt",):
                # Look for unpinned / loosely pinned deps
                loose = [ln.strip() for ln in content.splitlines()
                         if ln.strip() and not ln.strip().startswith("#")
                         and ln.strip() not in ("-e .",) and "==" not in ln and ">=" not in ln and "<=" not in ln and "~=" not in ln]
                if loose:
                    _add({
                        "file": rel, "severity": "medium",
                        "title": "Unpinned Python dependencies",
                        "detail": f"{len(loose)} packages are not pinned to an exact version (no '=='). "
                                  f"Examples: {', '.join(loose[:6])}. Unpinned deps can float and break builds.",
                        "evidence": f"file:{rel}"
                    })
                # Detect very loose upper bounds
                tight = []
                for ln in content.splitlines():
                    m = re.match(r"^\s*([\w\-.]+)([<>=!~]+)([0-9][\w.]*)", ln)
                    if m and any(ext in rel for ext in []) and "==" not in ln and ">=" in ln:
                        tight.append(ln.strip())
                if tight:
                    _add({
                        "file": rel, "severity": "low",
                        "title": "Floating minimum-bound dependencies",
                        "detail": f"{len(tight)} deps use '>=' which allows breaking major upgrades.",
                        "evidence": f"file:{rel}"
                    })

            elif manifest == "package.json":
                try:
                    import json
                    pkg = json.loads(content)
                    _check_package_json(rel, pkg, _add)
                except Exception:
                    pass

            elif manifest in ("pyproject.toml", "Pipfile", "Pipfile.lock", "Cargo.toml",
                              "go.mod", "package-lock.json"):
                # Minimal heuristic: flag 'dev' / 'pre' / 'beta' version markers as a risk signal
                prerelease = re.findall(r"['\"]?[0-9][\w.]*[-+](?:rc|beta|alpha|pre|dev)[\w.]*", content, re.IGNORECASE)
                if prerelease:
                    _add({
                        "file": rel, "severity": "low",
                        "title": "Pre-release dependency versions detected",
                        "detail": f"Pre-release markers found: {', '.join(sorted(set(prerelease))[:5])}. "
                                  "Pre-release packages may have unstable APIs and unannounced breaking changes.",
                        "evidence": f"file:{rel}"
                    })

    return findings


def _check_package_json(rel: str, pkg: Dict[str, Any], _add):
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    if not deps:
        return

    # Flag obvious glob/caret-only ranges that permit silent major upgrades
    caret_only = []
    for name, ver in deps.items():
        v = str(ver)
        if re.fullmatch(r"\^[0-9]+(\.[0-9]+)*", v) or re.fullmatch(r">=[0-9]+(\.[0-9]+)*", v):
            caret_only.append((name, v))
    if caret_only:
        _add({
            "file": rel, "severity": "medium",
            "title": "Caret (^) dependency ranges permit silent breaking upgrades",
            "detail": f"{len(caret_only)} deps use '^' or '>=' ranges. Example: "
                      f"{caret_only[0][0]}@{caret_only[0][1]}. Major versions >1.x can break at install time without notice.",
            "evidence": f"file:{rel}"
        })

    # Flag known-suspect packages (bundled native deps, heavy ML deps sometimes pinned oddly)
    suspicious = {}
    for name, ver in deps.items():
        n = name.lower()
        if "numpy" in n or "scikit" in n or "torch" in n or "tensorflow" in n or "pillow" in n:
            if str(ver) in ("*", "latest"):
                suspicious[name] = ver
    if suspicious:
        _add({
            "file": rel, "severity": "high",
            "title": "ML/native dependencies pinned to 'latest'",
            "detail": f"{', '.join(suspicious.keys())} are set to 'latest'/'*'. Native ML libs break frequently; "
                      "a rebuild can silently change numerical outputs.",
            "evidence": f"file:{rel}"
        })


def scan_recent_risk(root: str) -> List[Dict[str, Any]]:
    """Analyze git history for high-risk patterns: large diffs, hot authors, weekend/off-hours commits."""
    root = Path(root)
    findings: List[Dict[str, Any]] = []
    if not ((root / ".git").exists() or (root / ".git").is_file()):
        return findings

    # Author commit-count distribution
    code, out, _ = _run_git(["shortlog", "-sn", "-30", "HEAD"], cwd=str(root))
    authors = []
    if code == 0:
        for line in out.splitlines():
            parts = line.strip().split("\t")
            if len(parts) == 2 and parts[0].isdigit():
                authors.append({"name": parts[1], "commits": int(parts[0])})

    if authors:
        findings.append({
            "severity": "info",
            "title": "Commit activity concentration",
            "detail": f"Top contributor made {authors[0]['commits']} of the last ~30 commits. "
                      "Heavy single-author churn can create knowledge-silo risk and unreviewed changes.",
            "evidence": "git:shortlog"
        })

    # Files changed most often in recent history (change hotspots)
    code, out, _ = _run_git(["log", "-30", "--name-only", "--pretty=format:"], cwd=str(root))
    hotspots: Dict[str, int] = {}
    if code == 0:
        for line in out.splitlines():
            line = line.strip()
            if line and not line.endswith(".lock") and not line.startswith("docs/"):
                hotspots[line] = hotspots.get(line, 0) + 1
    hotspots = dict(sorted(hotspots.items(), key=lambda x: -x[1])[:5])
    if hotspots:
        top_file = max(hotspots, key=hotspots.get)
        findings.append({
            "severity": "medium",
            "title": "Frequently-changed files (change hotspots)",
            "detail": f"Most-changed files in the last 30 commits: {', '.join(list(hotspots)[:5])}. "
                      f"'{top_file}' is a likely source of regressions - high churn correlates with injected bugs.",
            "evidence": "git:name-only-changes"
        })

    # Weekend / off-hours commits (flag as lightly suspicious style signal)
    code, out, _ = _run_git(["log", "-50", "--pretty=format:%ad", "--date=iso"], cwd=str(root))
    offhours = 0
    total_days = 0
    if code == 0:
        for line in out.splitlines():
            try:
                if " " in line:
                    datepart = line.strip()
                    dt = datetime.strptime(datepart[:19], "%Y-%m-%d %H:%M:%S")
                    total_days += 1
                    if dt.weekday() >= 5 or dt.hour < 6 or dt.hour >= 22:
                        offhours += 1
            except Exception:
                continue
    if total_days >= 5 and offhours / total_days >= 0.3:
        findings.append({
            "severity": "low",
            "title": "High proportion of off-hours / weekend commits",
            "detail": f"{offhours}/{total_days} recent commits landed outside normal working hours. "
                      "These often bypass review and are richer error sources.",
            "evidence": "git:commit-timestamps"
        })

    return findings


def analyze_workspace(root: str) -> Dict[str, Any]:
    """Produce a full real-codebase analysis for the connected workspace."""
    metadata = get_repo_metadata(root)
    dep_findings = scan_dependency_risks(root)
    risk_findings = scan_recent_risk(root)

    all_findings = []
    for f in dep_findings + risk_findings:
        f["category"] = "dependency" if f in dep_findings else "git"
        all_findings.append(f)

    # Sort by severity so the most important come first
    sev_rank = {"high": 0, "medium": 1, "low": 2, "info": 3}
    all_findings.sort(key=lambda x: sev_rank.get(x.get("severity"), 4))

    return {
        "metadata": metadata,
        "findings": all_findings,
        "summary": _build_summary(metadata, all_findings),
    }


def _build_summary(metadata: Dict[str, Any], findings: List[Dict[str, Any]]) -> str:
    lines = []
    lines.append(f"Analyzed repository with {metadata['file_count']} files "
                 f"({metadata['code_file_count']} code files) across "
                 f"{', '.join(metadata['languages'].keys()) or 'unknown'} tech stack.")
    if metadata.get("branch"):
        lines.append(f"Git checkout: '{metadata['branch']}' with {metadata['total_commits']} commits in history.")
    if metadata.get("recent_commits"):
        lines.append(f"Latest commit: {metadata['recent_commits'][0]['message'][:60]} "
                     f"by {metadata['recent_commits'][0]['author']} ({metadata['recent_commits'][0]['date']}).")

    high = [f for f in findings if f.get("severity") == "high"]
    medium = [f for f in findings if f.get("severity") == "medium"]
    if high:
        lines.append(f"[{len(high)} HIGH-severity risk(s)] identified - most likely failure origins.")
    elif medium:
        lines.append(f"[{len(medium)} MEDIUM-severity risk(s)] identified.")
    else:
        lines.append("No HIGH/MEDIUM dependency risks detected in this snapshot.")

    return " | ".join(lines)


# ---------------------------------------------------------------------------
# Deep project understanding (architecture map + test discovery)
# ---------------------------------------------------------------------------

# Common entrypoint file names per runtime
ENTRYPOINT_PATTERNS = [
    ("main.py", "python"),
    ("app.py", "python"),
    ("manage.py", "django"),
    ("run.py", "python"),
    ("wsgi.py", "wsgi"),
    ("asgi.py", "asgi"),
    ("server.py", "python"),
    ("index.js", "node"),
    ("index.ts", "node"),
    ("server.js", "node"),
    ("server.ts", "node"),
    ("app.js", "node"),
    ("app.ts", "node"),
    ("main.go", "go"),
    ("src/main.rs", "rust"),
    ("run.rb", "ruby"),
    ("index.php", "php"),
    ("manage.py", "django"),
]

TEST_GLOB = ["test_*.py", "*_test.py", "*.test.js", "*.test.tsx", "*.test.ts",
             "*.spec.js", "*.spec.ts", "*_test.go", "test_*.rb"]


def detect_project_type(root: str) -> Dict[str, Any]:
    """Detect the overall project tech/tooling from top-level manifests."""
    root = Path(root)
    info = {
        "runtime": "unknown",
        "build_tool": None,
        "test_command": None,
        "package_manager": None,
        "description": "Could not confidently detect project type.",
        "manifests": [],
    }

    candidates = []
    for m in ["pyproject.toml", "requirements.txt", "package.json", "go.mod",
              "Cargo.toml", "Gemfile", "pom.xml", "build.gradle"]:
        p = root / m
        if p.exists():
            candidates.append((m, p))

    if not candidates:
        info["description"] = "No top-level build manifest detected."
        return info

    info["manifests"] = [m for m, _ in candidates]

    # Python
    if (root / "pyproject.toml").exists():
        info["runtime"] = "python"
        info["build_tool"] = "pyproject.toml"
        info["package_manager"] = "poetry/uv"
        # try to find pytest in config
        text = (root / "pyproject.toml").read_text(encoding="utf-8", errors="replace")
        info["test_command"] = "pytest" if ("pytest" in text or "[tool.pytest" in text) else None
    elif (root / "requirements.txt").exists():
        info["runtime"] = "python"
        info["build_tool"] = "requirements.txt"
        info["package_manager"] = "pip"
        info["test_command"] = "pytest" if (root / "pytest.ini").exists() or (root / "pyproject.toml").exists() else None

    # Node
    if (root / "package.json").exists():
        import json as _json
        try:
            pkg = _json.loads((root / "package.json").read_text(encoding="utf-8", errors="replace"))
        except Exception:
            pkg = {}
        info["runtime"] = "node"
        info["build_tool"] = "package.json"
        info["package_manager"] = pkg.get("packageManager") or ("npm" if "npm" in str(pkg.get("scripts", {})) else "npm")
        scripts = pkg.get("scripts", {})
        for key in ["test", "ci", "check"]:
            if key in scripts:
                info["test_command"] = f"npm run {key}"
                break
        if not info["test_command"]:
            info["test_command"] = "npm test"

    # Go
    if (root / "go.mod").exists():
        info["runtime"] = "go"
        info["build_tool"] = "go.mod"
        info["package_manager"] = "go mod"
        info["test_command"] = "go test ./..."

    # Rust
    if (root / "Cargo.toml").exists():
        info["runtime"] = "rust"
        info["build_tool"] = "Cargo.toml"
        info["package_manager"] = "cargo"
        info["test_command"] = "cargo test"

    info["description"] = (
        f"Detected a {info['runtime']} project managed by {info['build_tool'] or 'unknown tool'} "
        f"({info['package_manager'] or 'no package manager'}). "
        f"Test command: {info['test_command'] or 'none detected'}."
    )
    return info


def discover_entrypoints(root: str) -> List[Dict[str, Any]]:
    """Find likely application entrypoints (first entrypoint file wins)."""
    root = Path(root)
    found = []
    ignore = {".git", "node_modules", "dist", "build", "__pycache__", ".venv", "venv", "target", "vendor", ".idea", ".vscode"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ignore]
        for fname in filenames:
            rel = os.path.relpath(os.path.join(dirpath, fname), root)
            reln = rel.replace("\\", "/")
            for pat, kind in ENTRYPOINT_PATTERNS:
                if reln.endswith(pat) and len(reln.split("/")) <= 3:
                    found.append({"file": reln, "kind": kind, "module": reln.replace("/", ".").rsplit(".", 1)[0]})
                    break
            if len(found) >= 8:
                return found
    return found


def find_test_files(root: str) -> List[str]:
    """Find test files and directories in the project."""
    root = Path(root)
    tests = []
    ignore = {".git", "node_modules", "dist", "build", "__pycache__", ".venv", "venv", "target", "vendor"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ignore]
        for fname in filenames:
            reln = os.path.relpath(os.path.join(dirpath, fname), root).replace("\\", "/")
            for pat in TEST_GLOB:
                if reln.endswith(pat) and "/node_modules/" not in reln:
                    tests.append(reln)
                    break
        if len(tests) >= 60:
            break
    return sorted(tests)


def build_import_graph(root: str, max_nodes: int = 120) -> Dict[str, Any]:
    """Build a lightweight module dependency graph for Python / JS / TS files."""
    root = Path(root)
    nodes = []
    edges = []
    ignore = {".git", "node_modules", "dist", "build", "__pycache__", ".venv", "venv", "target", "vendor"}
    node_id = {}
    counter = [0]

    def _get_id(path_rel):
        key = path_rel
        if key not in node_id:
            idx = len(nodes)
            node_id[key] = idx
            nodes.append({"id": str(idx), "name": os.path.basename(path_rel), "path": path_rel})
        return str(node_id[key])

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ignore]
        for fname in filenames:
            if not fname.endswith((".py", ".js", ".ts", ".tsx", ".jsx")):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fname), root).replace("\\", "/")
            if rel.startswith((".git", "node_modules", "dist", "build", "__pycache__", ".venv", "venv")):
                continue
            _get_id(rel)
            if len(nodes) > max_nodes:
                break

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ignore]
        for fname in filenames:
            if not fname.endswith((".py", ".js", ".ts", ".tsx", ".jsx")):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fname), root).replace("\\", "/")
            if rel not in node_id:
                continue
            try:
                content = Path(root, rel).read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            imports = re.findall(r"^(?:import|from)\s+[\w.]+", content, re.M)
            src_dir = os.path.dirname(rel).replace("\\", "/")
            for line in imports:
                token = line.split()[1] if line.split()[0] == "import" else line.split()[1]
                core = token.split(".")[0]
                candidate = f"{src_dir}/{core}.py" if src_dir else f"{core}.py"
                if candidate in node_id and candidate != rel:
                    s = _get_id(rel); d = _get_id(candidate)
                    if s != d:
                        edges.append({"source": s, "target": d})

    # Identify hub modules (most dependents)
    dep_count = {}
    for e in edges:
        dep_count[e["target"]] = dep_count.get(e["target"], 0) + 1
    hubs = [nodes[int(k)] for k, _ in sorted(dep_count.items(), key=lambda x: -x[1])[:8]]

    return {"nodes": nodes, "edges": edges, "hub_modules": hubs}


def understand_project(root: str) -> Dict[str, Any]:
    """Produce a deep 'understanding' of a connected project: its architecture,
    entrypoints, services, dependencies, tests, and how the pieces fit together."""
    ptype = detect_project_type(root)
    entrypoints = discover_entrypoints(root)
    test_files = find_test_files(root)
    try:
        graph = build_import_graph(root)
    except Exception:
        graph = {"nodes": [], "edges": [], "hub_modules": []}
    metadata = get_repo_metadata(root)

    # Infer a high-level service/component map from top-level dirs
    top_dirs = metadata.get("top_dirs", [])
    services = []
    for d in top_dirs[:8]:
        services.append({"name": d, "role": _infer_dir_role(d)})

    return {
        "project_type": ptype,
        "entrypoints": entrypoints,
        "test_files": test_files,
        "test_file_count": len(test_files),
        "services": services,
        "module_graph": {"node_count": len(graph["nodes"]), "edge_count": len(graph["edges"]),
                         "hub_modules": graph["hub_modules"]},
        "summary": _build_understanding_summary(ptype, entrypoints, test_files, metadata, services),
    }


def _infer_dir_role(dirname: str) -> str:
    d = dirname.lower()
    if d in ("api", "routes", "controllers", "endpoints"):
        return "HTTP API / route handlers"
    if d in ("models", "domain", "entities"):
        return "Domain models / data entities"
    if d in ("services", "services", "usecases", "core", "logic"):
        return "Business logic / service layer"
    if d in ("frontend", "web", "ui", "components", "pages", "views"):
        return "Frontend / UI layer"
    if d in ("tests", "test", "spec", "__tests__"):
        return "Test suite"
    if d in ("infra", "infrastructure", "deploy", "k8s", "docker"):
        return "Infrastructure / deployment"
    if d in ("utils", "helpers", "lib", "common"):
        return "Shared utilities"
    if d in ("database", "db", "migrations", "migrate"):
        return "Database / migrations"
    if d in ("workers", "jobs", "cron", "tasks"):
        return "Background jobs / workers"
    if d in ("config", "conf", "settings"):
        return "Configuration"
    if d in ("ml", "models_ml", "inference", "predict"):
        return "ML / inference layer"
    return "Component"


def _build_understanding_summary(ptype, entrypoints, test_files, metadata, services) -> str:
    lines = []
    lines.append(ptype["description"])
    if entrypoints:
        eps = ", ".join(e["file"] for e in entrypoints[:4])
        lines.append(f"Entrypoints: {eps}.")
    else:
        lines.append("No clear application entrypoint detected (library/project).")
    if test_files:
        lines.append(f"{len(test_files)} test file(s) found - the agent can run these as its health gate.")
    else:
        lines.append("No test files found - health will rely on configured endpoint/metrics.")
    if services:
        lines.append("Top components: " + ", ".join(f"{s['name']} ({s['role']})" for s in services[:5]) + ".")
    if metadata.get("branch"):
        lines.append(f"On branch '{metadata['branch']}' with {metadata['total_commits']} commits.")
    return " ".join(lines)

