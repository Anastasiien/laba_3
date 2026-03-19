import docker
import socket
import logging
from typing import Optional

try:
    client = docker.from_env()
except Exception as e:
    print(f"[docker_manager] Ошибка подключения к Docker: {e}")
    client = None

logger = logging.getLogger(__name__)

def _get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def create_container(
    instance_id: str,
    os: str,
    cpu: int,
    ram_mb: int,
    ssh_port: int,
    public_key: str = "",
    username: str = "root"
) -> str:
    if not client:
        raise RuntimeError("Docker daemon is not available")

    container_name = f"lab_{instance_id}"

    try:
        old = client.containers.get(container_name)
        old.remove(force=True)
    except docker.errors.NotFound:
        pass

    setup_ssh_cmd = (
        "apt-get update && apt-get install -y openssh-server && "
        "mkdir -p /var/run/sshd && "
        "echo 'root:password123' | chpasswd && "
        "sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config && "
        "sed -i 's/UsePAM yes/UsePAM no/' /etc/ssh/sshd_config && "
        "/usr/sbin/sshd -D"
    )

    container = client.containers.run(
        image=os,
        name=container_name,
        detach=True,
        nano_cpus=cpu * 1_000_000_000,
        mem_limit=f"{ram_mb}m",
        ports={'22/tcp': ssh_port},
        entrypoint=["/bin/bash", "-c", setup_ssh_cmd],
        volumes={f"vol_{instance_id}": {'bind': '/root', 'mode': 'rw'}}
    )
    
    return container.id

def stop_container(container_id: str):
    if not client: return
    try:
        container = client.containers.get(container_id)
        container.stop()
        container.remove()
    except Exception as e:
        logger.error(f"Stop failed: {e}")

def restart_container(container_id: str):
    if not client: return
    try:
        container = client.containers.get(container_id)
        container.restart()
    except Exception as e:
        logger.error(f"Restart failed: {e}")

def get_cpu_time_sec(container_id: str) -> float:
    if not client: return 0.0
    try:
        container = client.containers.get(container_id)
        stats = container.stats(stream=False)
        cpu_usage = stats['cpu_stats']['cpu_usage']['total_usage']
        return round(cpu_usage / 1_000_000_000, 2)
    except Exception:
        return 0.0

def get_traffic_mb(container_id: str) -> float:
    if not client: return 0.0
    try:
        container = client.containers.get(container_id)
        stats = container.stats(stream=False)
        networks = stats.get("networks", {})
        total_bytes = 0
        for net in networks.values():
            total_bytes += net.get("rx_bytes", 0) + net.get("tx_bytes", 0)
        return round(total_bytes / (1024 * 1024), 2)
    except Exception:
        return 0.0