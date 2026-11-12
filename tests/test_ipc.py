import time
import unittest
from mimictype.core.ipc import IPCClient, IPCServer


class TestIPC(unittest.TestCase):

    def test_ipc_communication(self):
        received_commands = []

        def handler(req):
            cmd = req.get("command")
            received_commands.append(cmd)
            if cmd == "PING":
                return {"status": "PONG"}
            return {"echo": cmd}

        server = IPCServer(handler=handler)
        server.start()

        try:
            # Test ping
            self.assertTrue(IPCClient.ping())

            # Test command
            resp = IPCClient.send("TEST_CMD", {"param": 123})
            self.assertIsNotNone(resp)
            self.assertEqual(resp.get("echo"), "TEST_CMD")
            self.assertIn("PING", received_commands)
            self.assertIn("TEST_CMD", received_commands)
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
