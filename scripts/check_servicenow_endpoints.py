#!/usr/bin/env python3
import os
import sys
import json
from typing import List, Tuple

try:
    import requests
except ImportError:
    print("Missing dependency: requests. Install with `uv pip install requests` or `pip install requests`.")
    sys.exit(1)

try:
    from dotenv import load_dotenv, find_dotenv
except Exception:
    def load_dotenv(*args, **kwargs):
        return False
    def find_dotenv(*args, **kwargs):
        return None


def bool_from_env(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() not in {"false", "0", "no", "off"}


def get_env_or_exit() -> Tuple[str, str, str, bool]:
    load_dotenv(find_dotenv())
    base = os.getenv("SERVICENOW_INSTANCE_URL", "").rstrip("/")
    user = os.getenv("SERVICENOW_USERNAME", "")
    pwd = os.getenv("SERVICENOW_PASSWORD", "")
    verify_ssl = bool_from_env("SERVICENOW_VERIFY_SSL", True)

    missing = [n for n, v in [("SERVICENOW_INSTANCE_URL", base), ("SERVICENOW_USERNAME", user), ("SERVICENOW_PASSWORD", pwd)] if not v]
    if missing:
        print("Missing required env vars:", ", ".join(missing))
        sys.exit(2)
    return base, user, pwd, verify_ssl


def check(url: str, auth: Tuple[str, str], verify_ssl: bool) -> Tuple[int, str]:
    try:
        r = requests.get(url, auth=auth, verify=verify_ssl, timeout=30)
        return r.status_code, r.headers.get("content-type", "")
    except requests.RequestException as e:
        return -1, str(e)


def main() -> int:
    base, user, pwd, verify_ssl = get_env_or_exit()
    auth = (user, pwd)

    table_checks: List[Tuple[str, str]] = [
        ("Incidents list", f"{base}/api/now/table/incident?sysparm_limit=1"),
        ("Changes list", f"{base}/api/now/table/change_request?sysparm_limit=1"),
        ("Problems list", f"{base}/api/now/table/problem?sysparm_limit=1"),
    ]

    km_checks: List[Tuple[str, str]] = [
        ("KM search", f"{base}/api/sn_km_api/knowledge/articles?sysparm_limit=1"),
        ("KM featured", f"{base}/api/sn_km_api/knowledge/articles/featured?sysparm_limit=1"),
        ("KM mostviewed", f"{base}/api/sn_km_api/knowledge/articles/mostviewed?sysparm_limit=1"),
    ]

    print("ServiceNow endpoint checks:")
    print("- Base:", base)
    print("- Verify SSL:", verify_ssl)

    ok = True

    print("\nTable API:")
    for name, url in table_checks:
        code, ctype = check(url, auth, verify_ssl)
        ok = ok and (code == 200)
        print(f"  {name:<18} -> {code} {('('+ctype+')') if ctype else ''}")

    print("\nKnowledge API:")
    for name, url in km_checks:
        code, ctype = check(url, auth, verify_ssl)
        ok = ok and (code == 200)
        print(f"  {name:<18} -> {code} {('('+ctype+')') if ctype else ''}")

    print("\nResult:", "OK" if ok else "SOME FAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
