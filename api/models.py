from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class InstanceType(str, Enum):
    VM = "vm"
    CONTAINER = "container"

class InstanceStatus(str, Enum):
    CREATING = "creating"
    RUNNING = "running"
    STOPPED = "stopped"
    EXPIRED = "expired"
    RESTARTING = "restarting"
    ERROR = "error"

class StopReason(str, Enum):
    TIME_LIMIT = "time_limit"
    TRAFFIC_LIMIT = "traffic_limit"
    CPU_LIMIT = "cpu_limit"
    MANUAL = "manual"
    ERROR = "error"

class OSType(str, Enum):
    UBUNTU_22 = "ubuntu-22.04"
    UBUNTU_20 = "ubuntu-20.04"
    DEBIAN_12 = "debian-12"
    ALPINE = "alpine-3.18"
    FEDORA_38 = "fedora-38"

PRICE_PER_CPU_HOUR = 5.0
PRICE_PER_RAM_GB_HOUR = 2.0
PRICE_PER_DISK_GB_HOUR = 0.1

def calculate_price_per_hour(cpu: int, ram_mb: int, disk_gb: int) -> float:
    ram_gb = ram_mb / 1024
    price = (
        cpu * PRICE_PER_CPU_HOUR +
        ram_gb * PRICE_PER_RAM_GB_HOUR +
        disk_gb * PRICE_PER_DISK_GB_HOUR
    )
    return round(price, 2)

@dataclass
class ResourceLimits:
    cpu: int = 1
    ram_mb: int = 512
    disk_gb: int = 10
    time_limit_sec: int = 3600
    traffic_limit_mb: int = 1024
    cpu_time_limit_sec: int = 3600

@dataclass
class ResourceUsage:
    time_used_sec: int = 0
    traffic_used_mb: float = 0.0
    cpu_time_used_sec: float = 0.0

@dataclass
class SSHAccess:
    host: str = "localhost"
    port: int = 2222
    username: str = "user"
    password: str = "password123"

    def to_command(self) -> str:
        return f"ssh {self.username}@{self.host} -p {self.port}"

    def to_dict(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "command": self.to_command(),
        }

@dataclass
class Instance:
    id: str
    user_id: str
    name: str
    instance_type: InstanceType
    os: OSType
    limits: ResourceLimits
    ssh: SSHAccess

    status: InstanceStatus = InstanceStatus.CREATING
    usage: ResourceUsage = field(default_factory=ResourceUsage)
    created_at: datetime = field(default_factory=datetime.now)
    stopped_at: Optional[datetime] = None
    stop_reason: Optional[StopReason] = None

    qemu_pid: Optional[int] = None

    container_id: Optional[str] = None

    restart_count: int = 0

    def is_running(self) -> bool:
        return self.status == InstanceStatus.RUNNING

    def price_per_hour(self) -> float:
        return calculate_price_per_hour(
            self.limits.cpu,
            self.limits.ram_mb,
            self.limits.disk_gb,
        )

    def total_cost(self) -> float:
        hours = self.usage.time_used_sec / 3600
        return round(self.price_per_hour() * hours, 2)

    def time_remaining_sec(self) -> int:
        if self.limits.time_limit_sec == -1:
            return -1
        return max(0, self.limits.time_limit_sec - self.usage.time_used_sec)

    def traffic_remaining_mb(self) -> float:
        if self.limits.traffic_limit_mb == -1:
            return -1
        return max(0.0, self.limits.traffic_limit_mb - self.usage.traffic_used_mb)

    def cpu_time_remaining_sec(self) -> float:
        if self.limits.cpu_time_limit_sec == -1:
            return -1
        return max(0.0, self.limits.cpu_time_limit_sec - self.usage.cpu_time_used_sec)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.instance_type.value,
            "os": self.os.value,
            "status": self.status.value,
            "user_id": self.user_id,
            "cpu": self.limits.cpu,
            "ram_mb": self.limits.ram_mb,
            "disk_gb": self.limits.disk_gb,
            "ssh": self.ssh.to_dict(),
            "time_limit_sec": self.limits.time_limit_sec,
            "traffic_limit_mb": self.limits.traffic_limit_mb,
            "cpu_time_limit_sec": self.limits.cpu_time_limit_sec,
            "time_used_sec": self.usage.time_used_sec,
            "traffic_used_mb": round(self.usage.traffic_used_mb, 2),
            "cpu_time_used_sec": round(self.usage.cpu_time_used_sec, 2),
            "time_remaining_sec": self.time_remaining_sec(),
            "traffic_remaining_mb": self.traffic_remaining_mb(),
            "price_per_hour": self.price_per_hour(),
            "total_cost": self.total_cost(),
            "created_at": self.created_at.isoformat(),
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "stop_reason": self.stop_reason.value if self.stop_reason else None,
            "restart_count": self.restart_count,
        }
