#!/usr/bin/env python3
import os
import sys
import time
from typing import Tuple

try:
    import requests
except ImportError:
    print("Missing dependency: requests. Install with `uv pip install requests` or `pip install requests`.")
    sys.exit(1)

PORTS = [3001, 3002]
SSE_PATH = "/sse"
TIMEOUT = 5
STREAM_WINDOW_SEC = 1.5


def check_head(port: int) -> Tuple[bool, int, str]:
    url = f"http://localhost:{port}{SSE_PATH}"
    try:
        resp = requests.head(url, timeout=TIMEOUT, allow_redirects=False)
        ok = 200 <= resp.status_code < 400
        return ok, resp.status_code, "HEAD"
    except Exception as e:
        return False, 0, f"HEAD error: {e}"


def check_stream_open(port: int) -> Tuple[bool, int, str]:
    url = f"http://localhost:{port}{SSE_PATH}"
    try:
        with requests.get(url, timeout=TIMEOUT, stream=True) as r:
            # Connection established if status < 400; we don't consume the stream for long
            ok = 200 <= r.status_code < 400
            # Sleep briefly to ensure headers finished
            time.sleep(STREAM_WINDOW_SEC)
            return ok, r.status_code, "GET(stream)"
    except Exception as e:
        return False, 0, f"GET(stream) error: {e}"


def main() -> int:
    any_fail = False
    for port in PORTS:
        ok_h, code_h, info_h = check_head(port)
        ok_s, code_s, info_s = check_stream_open(port)
        status = "OK" if (ok_h and ok_s) else "FAIL"
        if not (ok_h and ok_s):
            any_fail = True
        print(f"Port {port}: {status} | {info_h}={code_h} | {info_s}={code_s}")
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
