"""国博余票监控主程序。"""
import random
import signal
import sys
import time
from datetime import datetime
from loguru import logger

from config import load_config
from museum_api import query_remaining
from notifier import notify_available


def _setup_logging() -> None:
    """日志输出到文件和控制台。"""
    logger.remove()
    logger.add(
        "logs/monitor.log",
        rotation="1 day",
        retention="7 days",
        encoding="utf-8",
        enqueue=True,
    )
    logger.add(lambda msg: print(msg, end=""), colorize=True)


def _is_rush_window(now: datetime | None = None) -> bool:
    """16:30-17:30 是放票前后高频时段。"""
    now = now or datetime.now()
    if now.hour == 16 and now.minute >= 30:
        return True
    return now.hour == 17


def _parse_targets(raw: str) -> set[str]:
    """解析配置里的目标日期字符串（逗号分隔）。"""
    return {d.strip() for d in raw.split(",") if d.strip()}


def _filter(results: list[dict], targets: set[str]) -> list[dict]:
    """按配置筛选可约日期。"""
    if targets:
        return [r for r in results if r["date"] in targets and r["available"]]
    return [r for r in results if r["available"]]


def _log_results(results: list[dict]) -> None:
    """逐行打印每日状态。"""
    for r in results:
        mark = "[OK]" if r["available"] else "[NO]"
        logger.info(f"  {mark} {r['date']} - {r['description']}")


def run_check(targets: set[str]) -> None:
    """执行一次余票检查 + 通知。"""
    logger.info("=" * 60)
    logger.info(f"开始检查余票 ({datetime.now():%Y-%m-%d %H:%M:%S})")

    results = query_remaining()
    if not results:
        logger.warning("查询无结果或失败")
        return

    _log_results(results)
    available = _filter(results, targets)

    if available:
        logger.success(f"🎉 发现 {len(available)} 天可预约！")
        notify_available(available)
    else:
        logger.info("当前无可预约日期")


def _install_signal_handler() -> None:
    """Ctrl+C 优雅退出。"""
    def handler(signum, frame):
        logger.info("用户中断，退出程序")
        sys.exit(0)
    signal.signal(signal.SIGINT, handler)


def main() -> None:
    _setup_logging()
    try:
        cfg = load_config()
    except FileNotFoundError:
        # config.py 里的 logger.error 已经输出过原因
        sys.exit(1)

    _install_signal_handler()

    interval_normal = cfg.getint("monitor", "interval_normal", fallback=600)
    interval_rush = cfg.getint("monitor", "interval_rush", fallback=30)
    targets = _parse_targets(cfg.get("monitor", "target_dates", fallback=""))

    if targets:
        logger.info(f"监控目标日期: {sorted(targets)}")
    else:
        logger.info("监控所有可预约日期")
    logger.info(f"普通频率: 每 {interval_normal} 秒 | 高峰频率: 每 {interval_rush} 秒")
    logger.info("按 Ctrl+C 退出")
    logger.info("")

    run_check(targets)

    while True:
        rush = _is_rush_window()
        interval = interval_rush if rush else interval_normal
        mode = "高峰" if rush else "普通"
        sleep_time = interval + random.uniform(-interval * 0.1, interval * 0.1)
        logger.info(f"[{mode}模式] 下次检查: 等待 {sleep_time:.0f} 秒")
        time.sleep(sleep_time)
        run_check(targets)


if __name__ == "__main__":
    main()
