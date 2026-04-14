from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import subprocess
import threading
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class _TargetSequenceHandler(BaseHTTPRequestHandler):
    responses: list[list[dict]] = []
    counter = 0
    lock = threading.Lock()

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/json/list":
            self.send_response(404)
            self.end_headers()
            return

        cls = type(self)
        with cls.lock:
            index = min(cls.counter, len(cls.responses) - 1)
            payload = cls.responses[index]
            cls.counter += 1

        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


class CdpTargetHelperTests(unittest.TestCase):
    def _pick_target(self, targets: list[dict], prefer: str = "") -> dict:
        script = f"""
const {{ pickInspectableTarget }} = require('./omnicontrol/runtime/scripts/cdp_target_helpers.js');
const targets = {json.dumps(targets)};
const target = pickInspectableTarget(targets, {json.dumps(prefer)});
console.log(JSON.stringify(target));
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)

    def test_prefers_url_match_when_title_is_empty(self) -> None:
        target = self._pick_target(
            [
                {
                    "type": "page",
                    "title": "",
                    "url": "vscode-file://vscode-app/setup.html",
                    "webSocketDebuggerUrl": "ws://preferred",
                },
                {
                    "type": "page",
                    "title": "Untitled",
                    "url": "about:blank",
                    "webSocketDebuggerUrl": "ws://fallback",
                },
            ],
            prefer="vscode-file://",
        )
        self.assertEqual(target["webSocketDebuggerUrl"], "ws://preferred")

    def test_prefers_page_over_service_worker(self) -> None:
        target = self._pick_target(
            [
                {
                    "type": "service_worker",
                    "title": "worker",
                    "url": "https://example.com/sw.js",
                    "webSocketDebuggerUrl": "ws://worker",
                },
                {
                    "type": "page",
                    "title": "App",
                    "url": "https://example.com/app",
                    "webSocketDebuggerUrl": "ws://page",
                },
            ]
        )
        self.assertEqual(target["webSocketDebuggerUrl"], "ws://page")

    def test_deprioritizes_devtools_targets(self) -> None:
        target = self._pick_target(
            [
                {
                    "type": "page",
                    "title": "DevTools - app",
                    "url": "devtools://devtools/bundled/inspector.html",
                    "webSocketDebuggerUrl": "ws://devtools",
                },
                {
                    "type": "page",
                    "title": "App",
                    "url": "chrome://new-tab-page/",
                    "webSocketDebuggerUrl": "ws://app",
                },
            ]
        )
        self.assertEqual(target["webSocketDebuggerUrl"], "ws://app")

    def test_waits_for_inspectable_target_to_appear(self) -> None:
        _TargetSequenceHandler.responses = [
            [],
            [{"type": "page", "title": "Untitled", "url": "about:blank"}],
            [
                {
                    "type": "page",
                    "title": "",
                    "url": "vscode-file://vscode-app/setup.html",
                    "webSocketDebuggerUrl": "ws://preferred",
                }
            ],
        ]
        _TargetSequenceHandler.counter = 0
        server = ThreadingHTTPServer(("127.0.0.1", 0), _TargetSequenceHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base_url = f"http://127.0.0.1:{server.server_port}"
            script = f"""
const {{ waitForInspectableTarget }} = require('./omnicontrol/runtime/scripts/cdp_target_helpers.js');
waitForInspectableTarget({json.dumps(base_url)}, 'vscode-file://', 3000, 50)
  .then((target) => {{
    console.log(JSON.stringify(target));
  }})
  .catch((error) => {{
    console.error(error.message);
    process.exit(1);
  }});
"""
            result = subprocess.run(
                ["node", "-e", script],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        payload = json.loads(result.stdout)
        self.assertEqual(payload["webSocketDebuggerUrl"], "ws://preferred")

    def test_waits_for_preferred_target_before_falling_back_when_requested(self) -> None:
        _TargetSequenceHandler.responses = [
            [
                {
                    "type": "page",
                    "title": "Blank",
                    "url": "about:blank",
                    "webSocketDebuggerUrl": "ws://fallback",
                }
            ],
            [
                {
                    "type": "page",
                    "title": "Blank",
                    "url": "about:blank",
                    "webSocketDebuggerUrl": "ws://fallback",
                }
            ],
            [
                {
                    "type": "page",
                    "title": "",
                    "url": "vscode-file://vscode-app/setup.html",
                    "webSocketDebuggerUrl": "ws://preferred",
                }
            ],
        ]
        _TargetSequenceHandler.counter = 0
        server = ThreadingHTTPServer(("127.0.0.1", 0), _TargetSequenceHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base_url = f"http://127.0.0.1:{server.server_port}"
            script = f"""
const {{ waitForInspectableTarget }} = require('./omnicontrol/runtime/scripts/cdp_target_helpers.js');
waitForInspectableTarget({json.dumps(base_url)}, 'vscode-file://', 3000, 50, false)
  .then((target) => {{
    console.log(JSON.stringify(target));
  }})
  .catch((error) => {{
    console.error(error.message);
    process.exit(1);
  }});
"""
            result = subprocess.run(
                ["node", "-e", script],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        payload = json.loads(result.stdout)
        self.assertEqual(payload["webSocketDebuggerUrl"], "ws://preferred")
        self.assertTrue(payload["__omniPreferMatched"])


if __name__ == "__main__":
    unittest.main()
