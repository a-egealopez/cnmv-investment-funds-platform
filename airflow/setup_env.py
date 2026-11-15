"""Create airflow/.env for the local Airflow setup, on any OS that runs Docker.

Runs inside a container (`docker compose run --rm airflow-setup`) with the repository
mounted at /project and the Docker socket mounted, so it reads the values Airflow needs
from Docker itself instead of from OS-specific shell commands:

- HOST_PROJECT_DIR: the repository path as the Docker daemon sees it, taken from this
  container's own /project mount. Airflow passes it to the stage containers.
- DOCKER_GID: group of the Docker socket inside a container.
- AIRFLOW_UID: owner of the repository, so files Airflow writes belong to the user.

An existing airflow/.env is never overwritten.
"""

import base64
import http.client
import json
import os
import secrets
import socket
import sys

PROJECT = "/project"
DOCKER_SOCK = "/var/run/docker.sock"
ENV_FILE = os.path.join(PROJECT, "airflow", ".env")
# Airflow's default user when the host does not map file ownership (Docker Desktop)
DEFAULT_UID = 50000


class _UnixConnection(http.client.HTTPConnection):
    def __init__(self, path: str):
        super().__init__("localhost")
        self.unix_path = path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.unix_path)


def host_project_dir() -> str:
    conn = _UnixConnection(DOCKER_SOCK)
    conn.request("GET", f"/containers/{socket.gethostname()}/json")
    mounts = json.loads(conn.getresponse().read())["Mounts"]
    return next(m["Source"] for m in mounts if m["Destination"] == PROJECT)


def main() -> int:
    if os.path.exists(ENV_FILE):
        print(f"{ENV_FILE} already exists; nothing to do")
        return 0

    uid = os.stat(PROJECT).st_uid or DEFAULT_UID
    values = {
        "AIRFLOW_UID": uid,
        "DOCKER_GID": os.stat(DOCKER_SOCK).st_gid,
        "HOST_PROJECT_DIR": host_project_dir(),
        "FERNET_KEY": base64.urlsafe_b64encode(os.urandom(32)).decode(),
        "API_SECRET_KEY": secrets.token_hex(32),
        "JWT_SECRET": secrets.token_hex(32),
    }
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(f"{key}={value}\n" for key, value in values.items())
    print(f"Created airflow/.env (HOST_PROJECT_DIR={values['HOST_PROJECT_DIR']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
