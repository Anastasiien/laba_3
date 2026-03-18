from typing import Dict, List, Optional
from api.models import Instance, InstanceStatus, InstanceType


_instances: Dict[str, Instance] = {}

def add_instance(instance: Instance) -> None:
    _instances[instance.id] = instance

def get_instance(instance_id: str) -> Optional[Instance]:
    return _instances.get(instance_id)

def update_instance(instance: Instance) -> None:
    _instances[instance.id] = instance

def remove_instance(instance_id: str) -> None:
    _instances.pop(instance_id, None)

def get_all_instances() -> List[Instance]:
    return list(_instances.values())

def get_running_instances() -> List[Instance]:
    return [i for i in _instances.values() if i.is_running()]

def get_instances_by_user(user_id: str) -> List[Instance]:
    return [i for i in _instances.values() if i.user_id == user_id]

def get_all_vms() -> List[Instance]:
    return [i for i in _instances.values() if i.instance_type == InstanceType.VM]

def get_all_containers() -> List[Instance]:
    return [i for i in _instances.values() if i.instance_type == InstanceType.CONTAINER]

def get_stats() -> dict:
    all_inst = get_all_instances()
    running = get_running_instances()
    return {
        "total": len(all_inst),
        "running": len(running),
        "stopped": len([i for i in all_inst if i.status == InstanceStatus.STOPPED]),
        "expired": len([i for i in all_inst if i.status == InstanceStatus.EXPIRED]),
        "error": len([i for i in all_inst if i.status == InstanceStatus.ERROR]),
        "vms": len(get_all_vms()),
        "containers": len(get_all_containers()),
        "total_cost": round(sum(i.total_cost() for i in all_inst), 2),
    }
