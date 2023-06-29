import os
import shutil
import tempfile
from typing import List

import docker
from fabric import Connection
from invoke import UnexpectedExit

from privateer.config import PrivateerHost, PrivateerTarget
from privateer.docker_helpers import DockerClient


def backup(host: PrivateerHost, targets: List[PrivateerTarget]):
    check_host_path(host)
    mounts = []
    if host.host_type == "remote":
        env = {
            "SSH_HOST_NAME": host.hostname,
            "SSH_REMOTE_PATH": host.path,
            "SSH_USER": host.user
        }
        mounts.append(docker.types.Mount("/root/.ssh", os.path.expanduser("~/.ssh"), type="bind"))
    else:
        mounts.append(docker.types.Mount("/archive", host.path, type="bind"))
        env = {}

    for t in targets:
        mounts.append(docker.types.Mount(f"/backup/{t.name}", t.name))
    with DockerClient() as cl:
        cl.containers.run(
            "offen/docker-volume-backup:v2",
            mounts=mounts,
            environment=env,
            detach=True,
            remove=True,
            entrypoint=["backup"]
        )
    return True


def restore(host: PrivateerHost, targets: List[PrivateerTarget]):
    success = []
    if host.host_type == "local":
        for t in targets:
            path = os.path.join(host.path, f"{t.name}.tar")
            if not os.path.exists(path):
                msg = f"Backup path '{path}' does not exist. Not restoring {t.name}"
                print(msg)
            else:
                untar_volume(t, host.path)
                success.append(t.name)
                print(f"Restored {path} to {t.name}")
    else:
        with Connection(host=host.hostname, user=host.user,
                        port=host.port) as c:
            with tempfile.TemporaryDirectory() as local_backup_path:
                for t in targets:
                    remote_path = os.path.join(host.path, f"{t.name}.tar")
                    try:
                        c.run(f"test -f {remote_path}", in_stream=False)
                        c.get(remote_path, f"{local_backup_path}/")
                        untar_volume(t, local_backup_path)
                        success.append(t.name)
                        print(f"Restored {remote_path} to {t.name}")
                    except UnexpectedExit:
                        msg = f"Backup path '{remote_path}' does not exist. Not restoring {t.name}"
                        print(msg)
    return success


def check_host_path(host: PrivateerHost):
    if host.host_type == "local":
        if not os.path.exists(host.path):
            msg = f"Host path '{host.path}' does not exist. Either make directory or fix config."
            raise Exception(msg)
    else:
        with Connection(host=host.hostname, user=host.user,
                        port=host.port) as c:
            try:
                c.run(f"test -d {host.path}", in_stream=False)
            except UnexpectedExit as err:
                msg = f"Host path '{host.path}' does not exist. Either make directory or fix config."
                raise Exception(msg) from err


def tar_volume(target: PrivateerTarget):
    tmp = tempfile.gettempdir()
    local_backup_path = os.path.join(tmp, "backup")
    if not os.path.exists(local_backup_path):
        os.mkdir(local_backup_path)
    volume_mount = docker.types.Mount("/data", target.name)
    backup_mount = docker.types.Mount("/backup", local_backup_path, type="bind")
    with DockerClient() as cl:
        cl.containers.run(
            "ubuntu",
            remove=True,
            mounts=[volume_mount, backup_mount],
            command=["tar", "cvf", f"/backup/{target.name}.tar", "-C", "/data",
                     "."],
        )
    return f"{local_backup_path}/{target.name}.tar"


def untar_volume(target: PrivateerTarget, backup_path):
    volume_mount = docker.types.Mount("/data", target.name)
    backup_mount = docker.types.Mount("/backup", backup_path, type="bind")
    with DockerClient() as cl:
        cl.containers.run(
            "ubuntu",
            remove=True,
            mounts=[volume_mount, backup_mount],
            command=["tar", "xvf", f"/backup/{target.name}.tar", "-C", "/data"],
        )
    return True
