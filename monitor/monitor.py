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
        running_instances = api.get_running_instances()
        
        for inst in running_instances:
            api.update_usage(inst.id, time_delta_sec=10)
            
            if inst.limits.cpu_time_limit_sec != -1:
                if inst.usage.cpu_time_used_sec >= inst.limits.cpu_time_limit_sec:
                    api.stop_instance(inst.id, reason=StopReason.CPU_LIMIT)

            from datetime import datetime
            uptime = (datetime.now() - inst.created_at).total_seconds()
            
            if inst.limits.time_limit_sec != -1:
                if uptime >= inst.limits.time_limit_sec:
                    api.stop_instance(inst.id, reason=StopReason.TIME_LIMIT)
                    continue

            if inst.limits.traffic_limit_mb != -1:
                if inst.usage.traffic_used_mb >= inst.limits.traffic_limit_mb:
                    api.stop_instance(inst.id, reason=StopReason.TRAFFIC_LIMIT)
                    continue
        
        time.sleep(10)