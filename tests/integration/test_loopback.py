"""Real HTTP/TCP integration. Uses temporary storage, temporary keys and child processes."""
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

SERVER_ROOT = Path(__file__).resolve().parents[2]
CLIENT_ROOT = Path(os.environ.get("CLIENT_REPO_PATH", str(SERVER_ROOT.parent / "climate-collector"))).resolve()
if not (CLIENT_ROOT / "client" / "uploader.py").exists():
    raise RuntimeError("Set CLIENT_REPO_PATH to the Client checkout for required HTTP integration tests")
sys.path.insert(0, str(CLIENT_ROOT))
from client.api_client import APIClient
from client.config import Config
from client.uploader import upload_file, UploadError
from client.worker import run_once
from client.metadata import save_json
from client.checksum import sha256_file


class LiveServer:
    def __init__(self, root):
        self.root = root
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self.process = None
        self.output = (root / "server.log").open("ab")

    def start(self):
        env = dict(os.environ, PYTHONPATH=str(SERVER_ROOT), PYTHONUTF8="1", DEBUG="False",
                   BASE_DIR=str(self.root), DATA_LAKE_DIR="data_lake", METADATA_DIR="metadata",
                   TEMP_DIR="data_lake/temp", COLLECTOR_API_KEY="integration-only-collector",
                   ADMIN_API_KEY="integration-only-admin", CLIENT01_API_KEY="", CLIENT02_API_KEY="",
                   ENABLE_LEGACY_KEYS="false", COLLECTOR_SOURCES='["usdm","noaa","usgs","nldas"]',
                   MAX_FILE_SIZE_BYTES="20971520", CHUNK_SIZE_BYTES="1048576")
        self.process = subprocess.Popen([sys.executable, "-m", "uvicorn", "server.main:app", "--host", "127.0.0.1",
            "--port", str(self.port)], cwd=self.root, env=env, stdout=self.output, stderr=self.output,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        deadline = time.monotonic() + 15
        with httpx.Client(timeout=0.5, trust_env=False) as http:
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError((self.root / "server.log").read_text(errors="replace"))
                try:
                    if http.get(self.url + "/health").status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                time.sleep(0.1)
        raise RuntimeError("Loopback server readiness timeout")

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill(); self.process.wait(timeout=5)

    def records(self):
        with sqlite3.connect(self.root / "metadata/ingestion.sqlite3") as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute("SELECT * FROM observations")]


@pytest.fixture
def live(tmp_path):
    storage = tmp_path / "server"; storage.mkdir()
    server = LiveServer(storage)
    try:
        server.start()
        yield server
    finally:
        server.stop(); server.output.close()


@pytest.fixture
def api(live, tmp_path):
    root = tmp_path / "client"; root.mkdir()
    api = APIClient(Config("collector01", "all", live.url, "integration-only-collector", timeout=2, retries=0, root=root))
    try:
        yield api
    finally:
        api.close()


def sample(api):
    path = api.config.root / "mock.csv"
    path.write_bytes(b"time,value\n2021-06-22,1.2\n")
    return path


def test_a_upload_and_integrity(live, api):
    path = sample(api)
    result = upload_file(api, path, "usdm", "2021-06-22")
    assert result["server_status"] == "VERIFIED" and result["listing_check"] == "matched"
    rows = live.records()
    assert len(rows) == 1 and rows[0]["client_id"] == "collector01"
    stored = live.root / rows[0]["stored_path"]
    assert sha256_file(stored) == sha256_file(path) == rows[0]["sha256"]
    assert stored.read_bytes() == path.read_bytes()


def test_b_duplicate(live, api):
    path = sample(api)
    first = upload_file(api, path, "usdm", "2021-06-22")
    again = upload_file(api, path, "usdm", "2021-06-22")
    assert again["server_status"] == "DUPLICATE" and again["server_file_id"] == first["server_file_id"]
    assert len(live.records()) == 1


def test_c_different_observation(live, api):
    path = sample(api)
    upload_file(api, path, "noaa", "2021-06-22")
    second = upload_file(api, path, "noaa", "2021-06-23")
    assert second["server_status"] == "VERIFIED" and len(live.records()) == 2
    assert len({row["stored_path"] for row in live.records()}) == 1


def test_d_offline_restart_worker(live, api):
    path = sample(api)
    live.stop()
    with pytest.raises(UploadError):
        upload_file(api, path, "usdm", "2021-06-22")
    jobs = list((api.config.root / "data/pending").iterdir())
    assert len(jobs) == 1
    job = jobs[0]; old_payload = (job / "payload").read_bytes()
    assert run_once(api)["server"] == "unavailable"
    live.start()
    metadata = json.loads((job / "metadata.json").read_text())
    # Advance the persisted deadline rather than waiting for backoff in the test.
    metadata["next_attempt_at"] = 0; save_json(job / "metadata.json", metadata)
    restarted = APIClient(api.config)
    try:
        report = run_once(restarted)
    finally:
        restarted.close()
    assert report["uploaded"] == [job.name]
    assert (api.config.root / "data/uploaded" / job.name / "payload").read_bytes() == old_payload
    assert live.records()[0]["original_filename"] == path.name and path.exists()


def test_e_multi_source(live, api):
    path = sample(api)
    for source in ["usdm", "noaa", "usgs", "nldas"]:
        assert upload_file(api, path, source, "2021-06-22")["server_status"] == "VERIFIED"
    assert {row["source"] for row in live.records()} == {"usdm", "noaa", "usgs", "nldas"}


def test_f_concurrent_client_processes(live, api, tmp_path):
    path = sample(api)
    code = '''
import sys, time, json
from pathlib import Path
from client.api_client import APIClient
from client.config import Config
from client.uploader import upload_file
url, root, file, deadline = sys.argv[1:]
api = APIClient(Config("collector01","all",url,"integration-only-collector",root=Path(root)))
try:
    time.sleep(max(0, float(deadline)-time.time()))
    result = upload_file(api, file, "usdm", "2021-06-22", dataset_key="concurrent")
    print(json.dumps({"status": result["server_status"], "file_id": result["server_file_id"]}))
finally:
    api.close()
'''
    children = []
    deadline = str(time.time() + 2)
    try:
        for i in range(2):
            children.append(subprocess.Popen([sys.executable, "-c", code, live.url, str(tmp_path / f"process{i}"), str(path), deadline],
                cwd=tmp_path, env=dict(os.environ, PYTHONPATH=str(CLIENT_ROOT), PYTHONUTF8="1"),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0))
        results = []
        for child in children:
            out, err = child.communicate(timeout=30)
            assert child.returncode == 0, err
            results.append(json.loads(out))
        assert sorted(row["status"] for row in results) == ["DUPLICATE", "VERIFIED"]
        assert len({row["file_id"] for row in results}) == 1 and len(live.records()) == 1
    finally:
        for child in children:
            if child.poll() is None:
                child.kill(); child.wait(timeout=5)
