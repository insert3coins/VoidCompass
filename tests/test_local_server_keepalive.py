"""The local page servers reuse connections instead of opening one per request.

Every overlay polls its server several times a second and the music
visualizer's levels travel fifteen times a second each way. With a new TCP
connection per request (every response said "Connection: close"), thousands
of loopback sockets sat in TIME_WAIT and Windows began refusing new ones:
the dashboard logged net::ERR_NO_BUFFER_SPACE and then went blank. A
connection is now kept for the next request, but only once the request's
body has been read in full, since an unread body would be parsed as the
next request line.
"""

from http.client import HTTPConnection
import json
from pathlib import Path
import unittest

from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer
from voidcompass.overlays.html_overlay_server import HtmlOverlayServer

WEB = Path(__file__).resolve().parents[1] / "web"


class LocalServerKeepAliveTests(unittest.TestCase):
    def connect(self, port):
        connection = HTTPConnection("127.0.0.1", port, timeout=5)
        self.addCleanup(connection.close)
        return connection

    def test_overlay_polls_share_one_connection(self):
        server = HtmlOverlayServer(WEB)
        self.addCleanup(server.stop)
        server.register("heartbeat", "heartbeat", "Heartbeat")
        connection = self.connect(server.port)
        sockets = set()
        for _ in range(40):
            connection.request("GET", f"/api/health?token={server.token}&overlay=heartbeat")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader("Connection"), "keep-alive")
            self.assertTrue(json.loads(response.read())["ok"])
            sockets.add(id(connection.sock))
        self.assertEqual(len(sockets), 1)

    def test_overlay_render_acknowledgements_keep_the_connection(self):
        server = HtmlOverlayServer(WEB)
        self.addCleanup(server.stop)
        server.register("heartbeat", "heartbeat", "Heartbeat")
        connection = self.connect(server.port)
        query = f"token={server.token}&overlay=heartbeat"
        for path, body in (("/api/rendered", {"revision": 1}), ("/api/ready", {}),
                           ("/api/host-status", {"ok": True})):
            connection.request("POST", f"{path}?{query}", body=json.dumps(body),
                               headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            response.read()
            self.assertEqual(response.status, 202, path)
            self.assertEqual(response.getheader("Connection"), "keep-alive", path)
        connection.request("GET", f"/api/health?{query}")
        self.assertEqual(connection.getresponse().status, 200)

    def test_dashboard_commands_share_one_connection(self):
        received = []
        server = HtmlDashboardServer(WEB / "dashboard",
                                     command_callback=lambda payload: received.append(payload) or True)
        self.addCleanup(server.stop)
        connection = self.connect(server.port)
        sockets = set()
        for index in range(30):
            connection.request("POST", f"/api/command?token={server.token}",
                               body=json.dumps({"action": "music_levels", "bands": [index] * 32}),
                               headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            response.read()
            self.assertEqual(response.status, 202)
            self.assertEqual(response.getheader("Connection"), "keep-alive")
            sockets.add(id(connection.sock))
        self.assertEqual(len(received), 30)
        self.assertEqual(received[-1]["bands"][0], 29)
        self.assertEqual(len(sockets), 1)

    def test_a_refused_post_closes_because_its_body_was_never_read(self):
        server = HtmlDashboardServer(WEB / "dashboard", command_callback=lambda payload: True)
        self.addCleanup(server.stop)
        connection = self.connect(server.port)
        connection.request("POST", "/api/command?token=wrong", body=json.dumps({"action": "x"}),
                           headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        response.read()
        self.assertEqual(response.status, 403)
        self.assertEqual(response.getheader("Connection"), "close")

    def test_a_client_that_asks_to_close_is_closed(self):
        server = HtmlOverlayServer(WEB)
        self.addCleanup(server.stop)
        connection = self.connect(server.port)
        connection.request("GET", "/assets/heartbeat-orb.js", headers={"Connection": "close"})
        response = connection.getresponse()
        response.read()
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Connection"), "close")

    def test_idle_connections_time_out(self):
        for server_class, root in ((HtmlOverlayServer, WEB), (HtmlDashboardServer, WEB / "dashboard")):
            with self.subTest(server=server_class.__name__):
                server = server_class(root)
                self.addCleanup(server.stop)
                self.assertTrue(0 < server._handler_type().timeout <= 120)


if __name__ == "__main__":
    unittest.main()
