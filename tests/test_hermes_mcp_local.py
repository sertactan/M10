from __future__ import annotations
import json
import threading
import http.client
from http.server import ThreadingHTTPServer
from core.hermes_team.mcp_local import handler_factory
from core.hermes_team.tasks import LocalTasks


def test_jsonrpc_initialize_tools_task_status(tmp_path, monkeypatch):
    from core.hermes_team import tasks
    monkeypatch.setattr(tasks, "perform_local_evidence_task",
                        lambda task: {"status": "INCONCLUSIVE", "llm_called": False})
    queue = LocalTasks(tmp_path / "jobs.sqlite3")
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory(queue, "z" * 40))
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
    finally:
        server.shutdown()
        server.server_close()
