import uuid
import random
from datetime import datetime
from typing import List, Optional
from qemu import qemu_manager

from api.models import (
    Instance, InstanceType, InstanceStatus, StopReason,
    OSType, ResourceLimits, ResourceUsage, SSHAccess,
    calculate_price_per_hour,
)
import api.state as state

try:
    import qemu.qemu_manager as qemu_manager
    QEMU_AVAILABLE = True
    print("[api] qemu_manager подключён")
except ImportError:
    QEMU_AVAILABLE = False
    print("[api] qemu_manager не найден — используем заглушку")

try:
    import docker.docker_manager as docker_manager
    DOCKER_AVAILABLE = True
    print("[api] docker_manager подключён")
except ImportError:
    DOCKER_AVAILABLE = False
    print("[api] docker_manager не найден — используем заглушку")

def _generate_id() -> str:
    return str(uuid.uuid4())[:8]

def _generate_ssh_port() -> int:
    used = {i.ssh.port for i in state.get_all_instances()}
    while True:
        port = random.randint(10000, 20000)
        if port not in used:
            return port

def create_vm(
    user_id: str,
    os: OSType,
    cpu: int,
    ram_mb: int,
    disk_gb: int,
    time_limit_sec: int  = 3600,
    traffic_limit_mb: int = 1024,
    cpu_time_limit_sec: int = 3600,
    name: Optional[str] = None,
) -> Instance:
    instance_id = _generate_id()
    ssh_port = _generate_ssh_port()

    instance = Instance(
        id = instance_id,
        user_id = user_id,
        name = name or f"vm-{instance_id}",
        instance_type = InstanceType.VM,
        os = os,
        limits = ResourceLimits(
            cpu = cpu,
            ram_mb = ram_mb,
            disk_gb = disk_gb,
            time_limit_sec = time_limit_sec,
            traffic_limit_mb = traffic_limit_mb,
            cpu_time_limit_sec = cpu_time_limit_sec,
        ),
        ssh = SSHAccess(
            host = "localhost",
            port = ssh_port,
            username = "user",
            password = "password123",
        ),
        status = InstanceStatus.CREATING,
    )

    state.add_instance(instance)

    if QEMU_AVAILABLE:
        try:
            image_path = qemu_manager.create_vm(
                instance_id = instance_id,
                os_type = os.value,
                cpu = cpu,
                ram_mb = ram_mb,
                disk_gb = disk_gb,
                ssh_port = ssh_port,
            )
            instance.image_path = image_path
            instance.status = InstanceStatus.RUNNING
        except Exception as e:
            instance.status = InstanceStatus.ERROR
            import traceback
            print(f"[api] Ошибка запуска VM {instance_id}: {e}")
            traceback.print_exc()
    else:
        instance.image_path = f"images/users/{user_id}/{instance_id}.qcow2"
        instance.status = InstanceStatus.RUNNING
        print(f"[api][STUB] VM {instance_id} создана")

    state.update_instance(instance)
    return instance


def create_container(
    user_id: str,
    os: OSType,
    cpu: int,
    ram_mb: int,
    time_limit_sec: int = 3600,
    traffic_limit_mb: int = 1024,
    cpu_time_limit_sec: int = 3600,
    name: Optional[str] = None,
) -> Instance:
    """
    Создать Docker контейнер.
    Возвращает Instance с SSH данными.
    """
    instance_id = _generate_id()
    ssh_port = _generate_ssh_port()

    instance = Instance(
        id = instance_id,
        user_id = user_id,
        name = name or f"container-{instance_id}",
        instance_type = InstanceType.CONTAINER,
        os = os,
        limits = ResourceLimits(
            cpu = cpu,
            ram_mb = ram_mb,
            disk_gb = 10,
            time_limit_sec = time_limit_sec,
            traffic_limit_mb = traffic_limit_mb,
            cpu_time_limit_sec = cpu_time_limit_sec,
        ),
        ssh = SSHAccess(
            host = "localhost",
            port = ssh_port,
            username = "root",
            password = "password123",
        ),
        status = InstanceStatus.CREATING,
    )

    state.add_instance(instance)

    if DOCKER_AVAILABLE:
        try:
            container_id = docker_manager.create_container(
                instance_id = instance_id,
                os = os.value,
                cpu = cpu,
                ram_mb = ram_mb,
                ssh_port = ssh_port,
            )
            instance.container_id = container_id
            instance.status = InstanceStatus.RUNNING
        except Exception as e:
            instance.status = InstanceStatus.ERROR
            print(f"[api] Ошибка запуска контейнера {instance_id}: {e}")
    else:
        instance.container_id = f"stub-container-{instance_id}"
        instance.status = InstanceStatus.RUNNING
        print(f"[api][STUB] Контейнер {instance_id} создан")

    state.update_instance(instance)
    return instance

def stop_instance(instance_id: str, reason: StopReason = StopReason.MANUAL) -> bool:
    instance = state.get_instance(instance_id)
    if not instance or not instance.is_running():
        return False

    success = _do_stop(instance)

    if success:
        instance.status = InstanceStatus.STOPPED if reason == StopReason.MANUAL else InstanceStatus.EXPIRED
        instance.stopped_at = datetime.now()
        instance.stop_reason = reason
        state.update_instance(instance)

    return success


def expire_instance(instance_id: str, reason: StopReason) -> bool:
    print(f"[api] ⚠ Инстанс {instance_id} погашен: {reason.value}")
    return stop_instance(instance_id, reason=reason)


def restart_instance(instance_id: str) -> bool:
    instance = state.get_instance(instance_id)
    if not instance:
        return False

    instance.status = InstanceStatus.RESTARTING
    state.update_instance(instance)

    success = False

    if instance.instance_type == InstanceType.VM:
        if QEMU_AVAILABLE:
            try:
                qemu_manager.restart_vm(instance_id)
                success = True
            except Exception as e:
                print(f"[api] Ошибка перезапуска VM {instance_id}: {e}")
        else:
            print(f"[api][STUB] VM {instance_id} перезапущена")
            success = True

    elif instance.instance_type == InstanceType.CONTAINER:
        if DOCKER_AVAILABLE:
            try:
                docker_manager.restart_container(instance.container_id)
                success = True
            except Exception as e:
                print(f"[api] Ошибка перезапуска контейнера {instance_id}: {e}")
        else:
            print(f"[api][STUB] Контейнер {instance_id} перезапущен")
            success = True

    if success:
        instance.status = InstanceStatus.RUNNING
        instance.usage = ResourceUsage()
        instance.restart_count += 1
        instance.stopped_at = None
        instance.stop_reason = None
    else:
        instance.status = InstanceStatus.ERROR

    state.update_instance(instance)
    return success


def _do_stop(instance: Instance) -> bool:
    """Внутренняя функция остановки — не вызывать напрямую"""
    if instance.instance_type == InstanceType.VM:
        if QEMU_AVAILABLE:
            try:
                qemu_manager.stop_vm(instance.id)
                return True
            except Exception as e:
                print(f"[api] Ошибка остановки VM: {e}")
                return False
        return True
    
    elif instance.instance_type == InstanceType.CONTAINER:
        if DOCKER_AVAILABLE:
            try:
                docker_manager.stop_container(instance.container_id)
                return True
            except Exception as e:
                print(f"[api] Ошибка остановки контейнера: {e}")
                return False
        return True

    return False

def update_usage(instance_id: str, time_delta_sec: int = 10) -> None:
    instance = state.get_instance(instance_id)
    if not instance or not instance.is_running():
        return

    instance.usage.time_used_sec += time_delta_sec

    if instance.instance_type == InstanceType.VM and QEMU_AVAILABLE:
        try:
            instance.usage.traffic_used_mb = qemu_manager.get_traffic_mb(instance_id)
        except Exception:
            pass
    elif instance.instance_type == InstanceType.CONTAINER and DOCKER_AVAILABLE:
        try:
            instance.usage.traffic_used_mb = docker_manager.get_traffic_mb(instance.container_id)
        except Exception:
            pass

    if instance.instance_type == InstanceType.VM and QEMU_AVAILABLE:
        try:
            instance.usage.cpu_time_used_sec = qemu_manager.get_cpu_time_sec(instance_id)
        except Exception:
            pass

    state.update_instance(instance)

def get_instance(instance_id: str) -> Optional[Instance]:
    return state.get_instance(instance_id)

def get_all_instances() -> List[Instance]:
    return state.get_all_instances()

def get_running_instances() -> List[Instance]:
    return state.get_running_instances()

def get_user_instances(user_id: str) -> List[Instance]:
    return state.get_instances_by_user(user_id)

def get_stats() -> dict:
    return state.get_stats()

def get_available_os() -> List[dict]:
    return [
        {"id": OSType.UBUNTU_22.value, "name": "Ubuntu 22.04 LTS"},
        {"id": OSType.UBUNTU_20.value, "name": "Ubuntu 20.04 LTS"},
        {"id": OSType.DEBIAN_12.value, "name": "Debian 12"},
        {"id": OSType.ALPINE.value,    "name": "Alpine Linux 3.18"},
        {"id": OSType.FEDORA_38.value, "name": "Fedora 38"},
    ]

def estimate_price(cpu: int, ram_mb: int, disk_gb: int) -> dict:
    per_hour = calculate_price_per_hour(cpu, ram_mb, disk_gb)
    return {
        "per_hour":  per_hour,
        "per_day":   round(per_hour * 24, 2),
        "per_month": round(per_hour * 24 * 30, 2),
    }
