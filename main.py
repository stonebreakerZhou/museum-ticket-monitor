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


EXHIBITIONS = {
    "1": ("基本陈列", 1, "免费常设展"),
    "2": ("庞贝特展", 750, "付费特展，公开 API 未单独覆盖"),
}

INTERVAL_PRESETS = [
    ("1", 5, "5 秒（极限频率，可能被限流）"),
    ("2", 10, "10 秒（高频）"),
    ("3", 15, "15 秒"),
    ("4", 30, "30 秒（放票前后高峰）"),
    ("5", 60, "60 秒"),
    ("6", 100, "100 秒（中频）"),
    ("7", 300, "5 分钟（推荐）"),
    ("8", 600, "10 分钟（省心）"),
]

MIN_INTERVAL = 5
MAX_INTERVAL = 3600


def _setup_logging() -> None:
    """日志输出：完整格式到文件，简化格式（仅消息）到控制台。"""
    logger.remove()
    logger.add(
        "logs/monitor.log",
        rotation="1 day",
        retention="7 days",
        encoding="utf-8",
        enqueue=True,
    )
    logger.add(sys.stderr, format="{message}", colorize=False)


def _parse_targets(raw: str) -> set[str]:
    """解析逗号分隔的日期字符串。"""
    return {d.strip() for d in raw.split(",") if d.strip()}


def _filter(results: list[dict], targets: set[str]) -> list[dict]:
    """按配置筛选可约日期。"""
    if targets:
        return [r for r in results if r["date"] in targets and r["available"]]
    return [r for r in results if r["available"]]


def _log_results(results: list[dict], targets: set[str]) -> None:
    """逐行打印每日状态。仅显示关注的日期，无 target 则全部显示。"""
    rows = results if not targets else [r for r in results if r["date"] in targets]
    for r in rows:
        mark = "[OK]" if r["available"] else "[NO]"
        logger.info(f"  {mark} {r['date']} - {r['description']}")


def run_check(targets: set[str], exhibition_name: str, hall_id: int) -> None:
    """执行一次余票检查 + 通知。"""
    logger.info("=" * 60)
    logger.info(f"开始检查余票 ({datetime.now():%Y-%m-%d %H:%M:%S})")

    results = query_remaining(hall_id=hall_id)
    if not results:
        logger.warning("查询无结果或失败")
        return

    _log_results(results, targets)
    available = _filter(results, targets)

    if available:
        logger.success(f"🎉 发现 {len(available)} 天可预约！")
        notify_available(available)
    else:
        logger.info("当前无可预约日期")


def _prompt_choice(prompt: str, options: list[tuple[str, str]], default: str) -> str:
    """显示选项并读取用户输入。"""
    for key, label in options:
        print(f"  {key}. {label}")
    while True:
        raw = input(f"{prompt} [{default}]: ").strip() or default
        if raw in {k for k, _ in options}:
            return raw
        print("  输入有误，请重新选择")


def _select_exhibition() -> str:
    """选择监控展厅，返回选项 key。"""
    print("请选择监控展厅：")
    options = [(k, f"{v[0]}（{v[2]}）") for k, v in EXHIBITIONS.items()]
    return _prompt_choice("请输入选项", options, default="1")


def _select_targets(cfg) -> set[str]:
    """读取重点关注的日期。"""
    default = cfg.get("monitor", "target_dates", fallback="").strip()
    default_hint = default if default else "（空=所有可约日期）"
    print(f"请输入重点关注的日期（YYYY-MM-DD，逗号分隔）")
    raw = input(f"默认 {default_hint}，直接回车: ").strip()
    return _parse_targets(raw) if raw else _parse_targets(default)


def _select_interval() -> int:
    """读取轮询间隔（秒）。"""
    print("请选择轮询间隔：")
    options = [(k, label) for k, _, label in INTERVAL_PRESETS]
    while True:
        key = _prompt_choice("请输入选项", options, default="7")
        seconds = next(v for k, v, _ in INTERVAL_PRESETS if k == key)
        if MIN_INTERVAL <= seconds <= MAX_INTERVAL:
            return seconds
        print(f"  间隔需在 {MIN_INTERVAL}-{MAX_INTERVAL} 秒之间")


def _install_signal_handler() -> None:
    """Ctrl+C 优雅退出。"""
    def handler(signum, frame):
        logger.info("用户中断，退出程序")
        sys.exit(0)
    signal.signal(signal.SIGINT, handler)


def _print_banner() -> None:
    """打印欢迎界面。"""
    print()
    print("=" * 50)
    print("  国博余票监控")
    print("=" * 50)
    print()


def main() -> None:
    _setup_logging()
    try:
        cfg = load_config()
    except FileNotFoundError:
        sys.exit(1)

    _install_signal_handler()
    _print_banner()

    key = _select_exhibition()
    exhibition_name, hall_id, _note = EXHIBITIONS[key]
    logger.info(f"已选展厅: {exhibition_name}（hallId={hall_id}）")
    print()

    targets = _select_targets(cfg)
    if targets:
        logger.info(f"重点关注: {sorted(targets)}")
    else:
        logger.info("监控所有可预约日期")
    print()

    interval = _select_interval()
    logger.info(f"轮询间隔: 每 {interval} 秒")
    print()

    logger.info("按 Ctrl+C 退出")
    logger.info("")

    run_check(targets, exhibition_name, hall_id)

    while True:
        sleep_time = interval + random.uniform(-interval * 0.1, interval * 0.1)
        logger.info(f"下次检查: 等待 {sleep_time:.0f} 秒")
        time.sleep(sleep_time)
        run_check(targets, exhibition_name, hall_id)


if __name__ == "__main__":
    main()
