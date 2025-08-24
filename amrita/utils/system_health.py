import os
import platform
import shutil
import sys

import psutil


def calculate_system_usage() -> dict:
    system_name = platform.system()
    system_version = platform.version()
    python_version = sys.version
    memory = psutil.virtual_memory()
    cpu_usage = psutil.cpu_percent(interval=1)
    logical_cores = psutil.cpu_count(logical=True)
    disk_usage_origin = shutil.disk_usage(os.getcwd())
    disk_usage = (disk_usage_origin.used / disk_usage_origin.total) * 100
    net_io = psutil.net_io_counters()

    return {
        "cpu_usage": cpu_usage,
        "memory_usage": memory.percent,
        "disk_usage": float(f"{disk_usage:.2f}"),
        "system_name": system_name,
        "system_version": system_version,
        "python_version": python_version,
        "logical_cores": logical_cores,
        "network_io": {"sent": net_io.bytes_sent, "received": net_io.bytes_recv},
    }


def calculate_system_health() -> dict:
    """
    计算系统健康值

    Returns:
        dict: 包含各项指标健康度和总体健康值的字典
    """
    # 获取CPU使用率
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_health = _calculate_cpu_health(cpu_percent)

    # 获取内存使用率
    memory_info = psutil.virtual_memory()
    memory_health = _calculate_memory_health(memory_info.percent)

    # 获取磁盘使用率
    disk_info = psutil.disk_usage("/")
    disk_percent = (disk_info.used / disk_info.total) * 100
    disk_health = _calculate_disk_health(disk_percent)

    # 获取关键进程状态
    process_health = _calculate_process_health()

    # 获取系统负载
    load_health = _calculate_load_health()

    # 计算总体健康值
    overall_health = (
        cpu_health * 0.25
        + memory_health * 0.25
        + disk_health * 0.25
        + process_health * 0.20
        + load_health * 0.05
    )

    # 确定健康等级
    health_level = _get_health_level(overall_health)

    return {
        "overall_health": round(overall_health, 2),
        "health_level": health_level,
        "details": {
            "cpu": {"usage": round(cpu_percent, 2), "health": cpu_health},
            "memory": {"usage": round(memory_info.percent, 2), "health": memory_health},
            "disk": {"usage": round(disk_percent, 2), "health": disk_health},
            "process": {"health": process_health},
            "load": {"health": load_health},
        },
    }


def _calculate_cpu_health(cpu_percent: float) -> float:
    """计算CPU健康度"""
    if cpu_percent <= 70:
        return 100.0
    elif cpu_percent <= 85:
        return 100.0 - (cpu_percent - 70) * 2
    else:
        health = 70.0 - (cpu_percent - 85) * 3
        return max(0.0, health)


def _calculate_memory_health(memory_percent: float) -> float:
    """计算内存健康度"""
    if memory_percent <= 80:
        return 100.0
    elif memory_percent <= 90:
        return 100.0 - (memory_percent - 80) * 2
    else:
        health = 80.0 - (memory_percent - 90) * 4
        return max(0.0, health)


def _calculate_disk_health(disk_percent: float) -> float:
    """计算磁盘健康度"""
    if disk_percent <= 85:
        return 100.0
    elif disk_percent <= 95:
        return 100.0 - (disk_percent - 85) * 1.5
    else:
        health = 85.0 - (disk_percent - 95) * 5
        return max(0.0, health)


def _calculate_process_health() -> float:
    """计算进程健康度（简化实现）"""
    try:
        # 获取所有进程数量
        process_count = len(list(psutil.process_iter()))

        # 简化处理：假设进程数量在正常范围内
        if process_count < 500:
            return 100.0
        elif process_count < 1000:
            return 90.0
        else:
            return 80.0
    except Exception:
        return 85.0


def _calculate_load_health() -> float:
    """计算系统负载健康度"""
    try:
        # 获取系统负载
        load_avg = os.getloadavg()
        load = load_avg[0]  # 1分钟平均负载

        # 获取CPU核心数
        cpu_count = psutil.cpu_count()

        # 处理cpu_count可能为None的情况
        if cpu_count is None:
            cpu_count = 1

        if load <= cpu_count * 0.7:
            return 100.0
        elif load <= cpu_count:
            return 100.0 - (load - cpu_count * 0.7) * 20
        else:
            health = 85.0 - (load - cpu_count) * 15
            return max(0.0, health)
    except Exception:
        return 85.0


def _get_health_level(health: float) -> str:
    """根据健康值确定健康等级"""
    if 90 <= health <= 100:
        return "Excellent"
    elif 75 <= health < 90:
        return "Good"
    elif 60 <= health < 75:
        return "Fair"
    elif 40 <= health < 60:
        return "Poor"
    else:
        return "Critical"
