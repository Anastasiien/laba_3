import time
import threading
from api import api
from api.models import StopReason, InstanceType

def start_monitoring():
    thread = threading.Thread(target=_monitor_loop, daemon=True)
    thread.start()
    print("[monitor] Фоновый мониторинг запущен")

def _monitor_loop():
    while True:
        # Получаем только работающие VM
        running_instances = api.get_running_instances()
        
        for inst in running_instances:
            if inst.instance_type == InstanceType.VM:
                # 1. Обновляем статистику
                api.update_usage(inst.id, time_delta_sec=10)
                
                # 2. Проверяем лимиты по свежим данным
                if inst.limits.cpu_time_limit_sec != -1:
                    if inst.usage.cpu_time_used_sec >= inst.limits.cpu_time_limit_sec:
                        api.expire_instance(inst.id, reason=StopReason.CPU_LIMIT)
        
        time.sleep(10)