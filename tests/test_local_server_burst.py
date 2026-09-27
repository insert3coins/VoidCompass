"""The local page servers must take the start-up burst without refusing it.

When the overlay host starts, every overlay page requests its document,
stylesheets and scripts at once; the dashboard page does the same with a
dozen files. At socketserver's default listen backlog of 5, Windows refused
part of that burst (WSAECONNREFUSED), so a launch could lose a page's script
and that overlay (the heartbeat, one day; the Navigation HUD's whole page on
another) never came up.
"""

from pathlib import Path
import socket
import threading
import unittest

from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer, _DashboardHTTPServer
from voidcompass.overlays.html_overlay_server import HtmlOverlayServer, _OverlayHTTPServer

WEB = Path(__file__).resolve().parents[1] / "web"
BURST = 80


def burst(port, path):
    """Fire BURST simultaneous requests; return the failures."""
    failures = []
    barrier = threading.Barrier(BURST)

    def client():
        barrier.wait()
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=10) as sock:
                sock.sendall(f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n".encode())
                data = b""
                while chunk := sock.recv(65536):
                    data += chunk
            if not data.startswith(b"HTTP/1.") or b" 200 " not in data.split(b"\r\n", 1)[0]:
                failures.append(data.split(b"\r\n", 1)[0].decode(errors="replace"))
        except OSError as exc:
            failures.append(f"{type(exc).__name__} {getattr(exc, 'winerror', '')}")

    threads = [threading.Thread(target=client) for _ in range(BURST)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return failures


class LocalServerBurstTests(unittest.TestCase):
    def test_both_servers_queue_a_startup_burst(self):
        for server_class in (_OverlayHTTPServer, _DashboardHTTPServer):
            with self.subTest(server=server_class.__name__):
                self.assertGreaterEqual(server_class.request_queue_size, 64)

    def test_overlay_server_answers_every_request_in_a_burst(self):
        server = HtmlOverlayServer(WEB)
        self.addCleanup(server.stop)
        for _ in range(3):
            self.assertEqual(burst(server.port, "/assets/heartbeat-orb.js"), [])

    def test_dashboard_server_answers_every_request_in_a_burst(self):
        server = HtmlDashboardServer(WEB / "dashboard")
        self.addCleanup(server.stop)
        for _ in range(3):
            self.assertEqual(burst(server.port, "/boot.css"), [])


if __name__ == "__main__":
    unittest.main()
