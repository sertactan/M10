from __future__ import annotations
import json
import threading
import http.client
import traceback
from core.hermes_team.mcp_local import handler_factory, LoopbackMCPServer
from core.hermes_team.tasks import LocalTasks


def test_jsonrpc_initialize_tools_task_status(tmp_path, monkeypatch):
    from core.hermes_team import tasks
    monkeypatch.setattr(tasks, "perform_local_evidence_task",
                        lambda task: {"status": "INCONCLUSIVE", "llm_called": False})
    queue = LocalTasks(tmp_path / "jobs.sqlite3")
    class RecordingServer(LoopbackMCPServer):
        errors = []

        def handle_error(self, request, client_address):
            self.errors.append(traceback.format_exc())

    server = RecordingServer(("127.0.0.1", 0), handler_factory(queue, "z" * 40))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def rpc(method, *, params=None, token=True):
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=4)
        try:
            connection.request("POST", "/mcp",
                               body=json.dumps({"jsonrpc": "2.0", "id": 1,
                                                "method": method, "params": params or {}}),
                               headers=({"Authorization": "Bearer " + "z" * 40}
                                        if token else {}))
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    try:
        assert rpc("tools/list", token=False)[0] == 401
        assert rpc("initialize")[1]["result"]["protocolVersion"] == "2025-03-26"
        assert len(rpc("tools/list")[1]["result"]["tools"]) == 5
        submitted = rpc("tools/call", params={"name": "meridyen_team_submit",
                                            "arguments": {"task": "scan"}})[1]
        job = json.loads(submitted["result"]["content"][0]["text"])["job_id"]
        result = rpc("tools/call", params={"name": "meridyen_team_tick"})[1]
        assert json.loads(result["result"]["content"][0]["text"])["status"] == "INCONCLUSIVE"
        status = rpc("tools/call", params={"name": "meridyen_team_job",
                                         "arguments": {"job_id": job}})[1]
        assert json.loads(status["result"]["content"][0]["text"])["state"] == "DONE"
        forbidden = rpc("tools/call", params={"name": "meridyen_team_submit",
                                             "arguments": {"task": "trade"}})[1]
        assert forbidden["result"]["isError"] is True
        assert server.errors == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_windows_loopback_real_http_repeated_handshakes(tmp_path):
    """No vendor data/localhost proxy, strong signal on socket failures."""
    queue = LocalTasks(tmp_path / "local-archive-free.sqlite3")
    activity = {"post": 0, "send": 0}
    base_handler = handler_factory(queue, "a" * 40)

    class DiagnosticHandler(base_handler):
        def do_POST(self):
            activity["post"] += 1
            return super().do_POST()

        def _send(self, code, payload):
            activity["send"] += 1
            return super()._send(code, payload)
    class Server(LoopbackMCPServer):
        errors = []
        accepted_count = 0

        def get_request(self):
            sock, address = super().get_request()
            self.accepted_count += 1
            return sock, address

        def handle_error(self, request, client_address):
            self.errors.append(traceback.format_exc())

    server = Server(("127.0.0.1", 0), DiagnosticHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for i in range(60):
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            try:
                authorized = bool(i % 2)
                connection.request(
                    "POST", "/mcp",
                    json.dumps({"jsonrpc": "2.0", "id": i, "method": "tools/list"}),
                    headers={"Authorization": "Bearer " + "a" * 40} if authorized else {},
                )
                try:
                    response = connection.getresponse()
                except (ConnectionResetError, ConnectionAbortedError, TimeoutError) as exc:
                    raise AssertionError(
                        f"LOOPBACK_SOCKET_RESET_ITER={i}, accepted_count={server.accepted_count}, "
                        f"server_thread_alive={thread.is_alive()}, activity={activity}, "
                        f"server_tracebacks={server.errors}"
                    ) from exc
                assert response.status == (200 if authorized else 401)
                data = json.loads(response.read())
                if authorized:
                    assert len(data["result"]["tools"]) == 5
            finally:
                connection.close()
        assert server.errors == [], "Server-side uncaught HTTP exception"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
