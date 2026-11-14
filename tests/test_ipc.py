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

            # Test >64 KiB framed payload (128 KiB)
            large_text = "x" * (128 * 1024)
            resp_large = IPCClient.send("LARGE", {"text": large_text})
            self.assertIsNotNone(resp_large)
            self.assertEqual(resp_large.get("echo"), "LARGE")
        finally:
            server.stop()

    def test_large_payload_echo_over_128kb(self):
        def handler(req):
            return {"len": len(req.get("text", "")), "sample": req.get("text", "")[-8:]}

        server = IPCServer(handler=handler)
        server.start()
        try:
            payload = "A" * 150_000 + "TAIL_END"
            resp = IPCClient.send("TYPE", {"text": payload})
            self.assertEqual(resp, {"len": len(payload), "sample": "TAIL_END"})
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
