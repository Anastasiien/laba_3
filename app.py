import streamlit as st
import time
from api import api
from api.models import OSType, InstanceType

@st.cache_resource
def start_system():
    try:
        from monitor import monitor
        monitor.start_monitoring()
        print("[System] Фоновый мониторинг успешно запущен из Streamlit")
    except Exception as e:
        print(f"[System] Ошибка запуска монитора: {e}")
    return True

start_system()

st.set_page_config(page_title="Cloud Hosting Provider", layout="wide")

st.markdown(
    """
    <style>
    .stApp { background-color: #E3F2FD; }
    [data-testid="stSidebar"] { background-color: #BBDEFB; }
    .streamlit-expanderHeader {
        background-color: white !important;
        border-radius: 10px;
        border: 1px solid #90CAF9;
    }
    .streamlit-expanderContent {
        background-color: white !important;
        border-bottom-left-radius: 10px;
        border-bottom-right-radius: 10px;
    }
    h1, h2, h3 { color: #1565C0; }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("Панель управления хостингом")

st.sidebar.header("Настройки")
user_id = st.sidebar.text_input("ID Пользователя", value="user_1")
name = st.sidebar.text_input("Название", value="My Instance")
inst_type = st.sidebar.selectbox("Тип", ["VM", "Container"])

available_os_data = api.get_available_os()
os_options = {os['name']: os['id'] for os in available_os_data}
selected_os_name = st.sidebar.selectbox("Операционная система", options=list(os_options.keys()))
selected_os_id = os_options[selected_os_name]

cpu = st.sidebar.slider("CPU (cores)", 1, 4, 1)
ram = st.sidebar.slider("RAM (MB)", 128, 2048, 512, step=128)

if inst_type == "VM":
    disk = st.sidebar.slider("Disk (GB)", 5, 50, 10)
    limit = st.sidebar.number_input("Лимит CPU (сек)", 10, 3600, 60)
else:
    disk = 10
    limit = st.sidebar.number_input("Лимит CPU (сек)", 10, 3600, 30)


st.sidebar.markdown("---")
st.sidebar.subheader("Предварительный расчет")
pricing = api.estimate_price(cpu, ram, disk)
st.sidebar.write(f"**В час:** {pricing['per_hour']} ₽")
st.sidebar.write(f"**В сутки:** {pricing['per_day']} ₽")

if inst_type == "VM":
    if st.sidebar.button("Запустить VM"):
        with st.spinner("Создаем виртуальную машину..."):
            new_vm = api.create_vm(user_id, OSType(selected_os_id), cpu, ram, disk, cpu_time_limit_sec=limit, name=name)
            st.sidebar.success(f"VM {new_vm.id} запущен!")
else:
    if st.sidebar.button("Запустить Контейнер"):
        with st.spinner("Разворачиваем контейнер..."):
            new_ct = api.create_container(user_id, OSType(selected_os_id), cpu, ram, cpu_time_limit_sec=limit, name=name)
            st.sidebar.success(f"Контейнер {new_ct.id} запущен!")

st.header("Ваши активные ресурсы")

if st.button("Обновить список"):
    st.rerun()

instances = api.get_all_instances()

if not instances:
    st.info("У вас пока нет запущенных машин или контейнеров.")
else:
    for inst in instances:
        price_per_hour = api.calculate_price_per_hour(
            inst.limits.cpu, inst.limits.ram_mb, inst.limits.disk_gb
        )
        total_spent = round((price_per_hour / 3600) * inst.usage.cpu_time_used_sec, 2)

        with st.expander(f"{inst.name} (ID: {inst.id}) — {inst.status.value}"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write(f"**Тип:** {inst.instance_type.value}")
                st.write(f"**ОС:** `{inst.os.value}`")
                st.write(f"**Накоплено:** `{total_spent} ₽`")
                st.write(f"**SSH:** `{inst.ssh.username}@{inst.ssh.host}:{inst.ssh.port}`")
            
            with col2:
                usage_percent = min(inst.usage.cpu_time_used_sec / inst.limits.cpu_time_limit_sec, 1.0)
                st.write(f"**CPU Time:** {inst.usage.cpu_time_used_sec:.2f} / {inst.limits.cpu_time_limit_sec}s")
                st.progress(usage_percent)
                st.write(f"**Трафик:** {inst.usage.traffic_used_mb} MB")
            
            with col3:
                if inst.is_running():
                    if st.button("Stop", key=f"stop_{inst.id}"):
                        api.stop_instance(inst.id)
                        st.rerun()
                    if st.button("Restart", key=f"re_{inst.id}"):
                        api.restart_instance(inst.id)
                        st.rerun()
                else:
                    reason = inst.stop_reason.value if inst.stop_reason else "Unknown"
                    st.error(f"Остановлен: {reason}")

time.sleep(5)
st.rerun()