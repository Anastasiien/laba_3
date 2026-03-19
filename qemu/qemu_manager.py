import subprocess
import os
import signal
import psutil
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIDS_DIR = os.path.join(BASE_DIR, "qemu/pids")
IMAGES_BASE = os.path.join(BASE_DIR, "images/base")
IMAGES_ACTIVE = os.path.join(BASE_DIR, "images/active")

os.makedirs(PIDS_DIR, exist_ok=True)
os.makedirs(IMAGES_ACTIVE, exist_ok=True)

def _run_qemu_process(instance_id, user_img, ram_mb, cpu, ssh_port):
    pid_file = os.path.join(PIDS_DIR, f"{instance_id}.pid")

    cmd = ["qemu-system-x86_64", "-m", str(ram_mb), "-smp", str(cpu), "-drive", f"file={user_img},format=qcow2",
        "-net", "nic", "-net", f"user,hostfwd=tcp::{ssh_port}-:22", "-display", "none", "-daemonize", "-pidfile", pid_file]
    
    if os.path.exists("/dev/kvm") and os.access("/dev/kvm", os.W_OK): 
        cmd.extend(["-accel", "kvm"])
    else:
        cmd.extend(["-accel", "tcg"])
    
    subprocess.Popen(cmd)
    return pid_file

def create_vm(instance_id, os_type, cpu, ram_mb, disk_gb, ssh_port):
    base_img = os.path.join(IMAGES_BASE, f"{os_type}.qcow2")
    user_img = os.path.join(IMAGES_ACTIVE, f"{instance_id}.qcow2")

    if not os.path.exists(base_img):
        raise FileNotFoundError(f"Базовый образ не найден: {base_img}")

    if not os.path.exists(user_img):
        subprocess.run([
            "qemu-img", "create", "-f", "qcow2", 
            "-b", base_img, "-F", "qcow2", user_img
        ], check=True)

    _run_qemu_process(instance_id, user_img, ram_mb, cpu, ssh_port)
    return user_img

def stop_vm(instance_id):
    pid_file = os.path.join(PIDS_DIR, f"{instance_id}.pid")
    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
            
            proc = psutil.Process(pid)
            proc.terminate()
            
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                proc.kill()
                
        except (psutil.NoSuchProcess, ProcessLookupError, ValueError): 
            pass
        finally:
            if os.path.exists(pid_file): 
                os.remove(pid_file)

def restart_vm(instance_id, ram_mb, cpu, ssh_port):
    """Перезапуск: Стоп + Старт без пересоздания диска"""
    stop_vm(instance_id)
    time.sleep(1)
    
    user_img = os.path.join(IMAGES_ACTIVE, f"{instance_id}.qcow2")
    if not os.path.exists(user_img):
        raise FileNotFoundError(f"Не удается перезапустить: диск {user_img} потерян")
        
    _run_qemu_process(instance_id, user_img, ram_mb, cpu, ssh_port)

def get_cpu_time_sec(instance_id):
    pid_file = os.path.join(PIDS_DIR, f"{instance_id}.pid")
    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
            return psutil.Process(pid).cpu_times().user
        except (psutil.NoSuchProcess, ProcessLookupError, FileNotFoundError, ValueError): 
            return 0.0
    return 0.0