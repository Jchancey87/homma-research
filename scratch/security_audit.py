import os
import re
import ast
import json
import subprocess

PROJECT_ROOT = "/home/jackc/projects/homma-research"

results = {
    "git_tracked_secrets": [],
    "hardcoded_secrets": [],
    "sql_injection_risks": [],
    "command_injection_risks": [],
    "path_traversal_risks": [],
    "ssrf_risks": [],
    "unsafe_deserialization": [],
    "xss_risks": [],
    "auth_router_analysis": [],
    "cors_and_network": [],
    "file_permissions": []
}

# 1. Check Git Tracked Files for sensitive patterns / .env / backups / sql
try:
    git_files = subprocess.check_output(["git", "ls-files"], cwd=PROJECT_ROOT, text=True).splitlines()
    for f in git_files:
        if f.endswith(".env") or f.endswith(".pem") or f.endswith(".key") or f.endswith(".sql") or "token" in f.lower() or "secret" in f.lower():
            results["git_tracked_secrets"].append(f)
except Exception as e:
    results["git_tracked_secrets"].append(f"Git check error: {str(e)}")

# Regex patterns for secret detection
SECRET_PATTERNS = [
    (re.compile(r"""(?i)(api[_-]?key|secret[_-]?key|password|bearer|auth[_-]?token|private[_-]?key)\s*[:=]\s*['"]([^'"]{6,})['"]"""), "Potential hardcoded secret key"),
    (re.compile(r"""(?i)https?://[^:\s"']+:[^@\s"']+@[^/\s"']+"""), "Embedded DB/service credentials in URL"),
    (re.compile(r"""-----BEGIN (RSA|OPENSSH|EC|PGP) PRIVATE KEY-----"""), "Private Key Block"),
]

# SQL Injection regex
SQL_INJECTION_PATTERNS = [
    (re.compile(r"""(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE)\s+.*?\s+(WHERE|VALUES|SET|FROM).*?(f['"]|%s|\.format|\+)"""), "Dynamic string construction in SQL query"),
    (re.compile(r"""conn\.(execute|fetch|fetchrow|fetchval)\(\s*f['"]"""), "f-string inside asyncpg query call"),
    (re.compile(r"""cursor\.(execute)\(\s*f['"]"""), "f-string inside cursor query call"),
]

# Command Injection regex
CMD_INJECTION_PATTERNS = [
    (re.compile(r"""subprocess\.(Popen|run|call|check_output)\([^)]*shell\s*=\s*True"""), "subprocess call with shell=True"),
    (re.compile(r"""os\.system\("""), "os.system usage"),
    (re.compile(r"""os\.popen\("""), "os.popen usage"),
]

# Unsafe Deserialization & Code Exec
UNSAFE_EXEC_PATTERNS = [
    (re.compile(r"""\beval\("""), "eval() call"),
    (re.compile(r"""\bexec\("""), "exec() call"),
    (re.compile(r"""pickle\.(loads|load)\("""), "pickle deserialization"),
    (re.compile(r"""yaml\.load\([^)]*Loader\s*=\s*yaml\.(Loader|UnsafeLoader)"""), "unsafe yaml loading"),
]

# Path Traversal
PATH_TRAVERSAL_PATTERNS = [
    (re.compile(r"""FileResponse\("""), "FileResponse usage - check path sanitization"),
    (re.compile(r"""send_file\("""), "send_file usage"),
    (re.compile(r"""open\([^)]*request\."""), "Direct file open from request object"),
]

# SSRF
SSRF_PATTERNS = [
    (re.compile(r"""(httpx|requests|aiohttp)\.(get|post|put|delete|patch|head)\(\s*([a-zA-Z0-9_]+)"""), "HTTP request call using dynamic URL variable"),
]

# XSS in Frontend
XSS_PATTERNS = [
    (re.compile(r"""dangerouslySetInnerHTML"""), "dangerouslySetInnerHTML usage"),
    (re.compile(r"""href=\{`javascript:"""), "javascript: link scheme"),
]

EXCLUDE_DIRS = {".git", "node_modules", ".pytest_cache", "__pycache__", ".next", "venv", "dist", "build"}

def scan_file(filepath):
    rel_path = os.path.relpath(filepath, PROJECT_ROOT)
    # Skip scratch security audit itself
    if "security_audit.py" in rel_path:
        return
    
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            lines = content.splitlines()

        for line_num, line in enumerate(lines, 1):
            # Check secrets (excluding example envs or docs if needed, but flag them if suspicious)
            if not rel_path.endswith(".example") and not rel_path.endswith(".md"):
                for pattern, msg in SECRET_PATTERNS:
                    if pattern.search(line):
                        # Filter out false positives like dummy test placeholders
                        if "example" not in line.lower() and "your_" not in line.lower() and "xxx" not in line.lower() and "placeholder" not in line.lower():
                            results["hardcoded_secrets"].append({"file": rel_path, "line": line_num, "code": line.strip()[:120], "issue": msg})

            # Check SQL Injection
            if filepath.endswith(".py"):
                for pattern, msg in SQL_INJECTION_PATTERNS:
                    if pattern.search(line):
                        results["sql_injection_risks"].append({"file": rel_path, "line": line_num, "code": line.strip()[:120], "issue": msg})

            # Check Command Injection
            if filepath.endswith(".py") or filepath.endswith(".sh") or filepath.endswith(".js"):
                for pattern, msg in CMD_INJECTION_PATTERNS:
                    if pattern.search(line):
                        results["command_injection_risks"].append({"file": rel_path, "line": line_num, "code": line.strip()[:120], "issue": msg})

            # Check Unsafe Exec / Pickle
            if filepath.endswith(".py"):
                for pattern, msg in UNSAFE_EXEC_PATTERNS:
                    if pattern.search(line):
                        results["unsafe_deserialization"].append({"file": rel_path, "line": line_num, "code": line.strip()[:120], "issue": msg})

            # Check Path Traversal
            if filepath.endswith(".py"):
                for pattern, msg in PATH_TRAVERSAL_PATTERNS:
                    if pattern.search(line):
                        results["path_traversal_risks"].append({"file": rel_path, "line": line_num, "code": line.strip()[:120], "issue": msg})

            # Check SSRF
            if filepath.endswith(".py"):
                for pattern, msg in SSRF_PATTERNS:
                    if pattern.search(line):
                        # Filter out internal or hardcoded constant URLs
                        if "http" in line and not ("localhost" in line or "127.0.0.1" in line or 'api.schwab.com' in line or 'financialmodelingprep.com' in line or 'sec.gov' in line):
                            results["ssrf_risks"].append({"file": rel_path, "line": line_num, "code": line.strip()[:120], "issue": msg})

            # Check XSS
            if filepath.endswith(".tsx") or filepath.endswith(".jsx") or filepath.endswith(".js") or filepath.endswith(".html"):
                for pattern, msg in XSS_PATTERNS:
                    if pattern.search(line):
                        results["xss_risks"].append({"file": rel_path, "line": line_num, "code": line.strip()[:120], "issue": msg})

    except Exception as e:
        pass

for root, dirs, files in os.walk(PROJECT_ROOT):
    dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
    for file in files:
        filepath = os.path.join(root, file)
        scan_file(filepath)

# 2. FastAPI Routers Authentication Analysis
routers_dir = os.path.join(PROJECT_ROOT, "backend", "fastapi_app", "routers")
if os.path.exists(routers_dir):
    for r_file in os.listdir(routers_dir):
        if r_file.endswith(".py"):
            r_path = os.path.join(routers_dir, r_file)
            try:
                with open(r_path, "r", encoding="utf-8") as f:
                    code = f.read()
                
                # Count routes and check for auth dependencies
                tree = ast.parse(code)
                routes = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        for dec in node.decorator_list:
                            dec_str = ast.unparse(dec) if hasattr(ast, "unparse") else ""
                            if any(m in dec_str for m in ["router.get", "router.post", "router.put", "router.delete", "router.patch"]):
                                # Check if function has authentication dependency
                                args_str = ast.unparse(node.args) if hasattr(ast, "unparse") else ""
                                has_auth = "Depends" in args_str or "get_current_user" in args_str or "api_key" in args_str or "verify_token" in args_str
                                routes.append({
                                    "endpoint_fn": node.name,
                                    "decorator": dec_str,
                                    "has_auth_dep": has_auth
                                })
                results["auth_router_analysis"].append({
                    "router": r_file,
                    "route_count": len(routes),
                    "routes": routes
                })
            except Exception as e:
                results["auth_router_analysis"].append({"router": r_file, "error": str(e)})

# 3. Check CORS & App Setup in main.py
main_py = os.path.join(PROJECT_ROOT, "backend", "fastapi_app", "main.py")
if os.path.exists(main_py):
    with open(main_py, "r", encoding="utf-8") as f:
        main_content = f.read()
        if "CORSMiddleware" in main_content:
            results["cors_and_network"].append("CORSMiddleware present in main.py")
            if 'allow_origins=["*"]' in main_content or "allow_origins=['*']" in main_content:
                results["cors_and_network"].append("CRITICAL/WARNING: Wildcard CORS origin allow_origins=['*'] detected!")
            if "allow_credentials=True" in main_content and ('allow_origins=["*"]' in main_content or "allow_origins=['*']" in main_content):
                results["cors_and_network"].append("CRITICAL: Wildcard CORS with allow_credentials=True is invalid or insecure!")

# Output report as JSON
out_path = os.path.join(PROJECT_ROOT, "scratch", "security_audit_raw.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print(f"Audit completed. Raw output written to {out_path}")
