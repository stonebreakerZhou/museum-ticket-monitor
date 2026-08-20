"""通知模块。检测到有余票时通过 Server酱（微信）或邮件通知用户。"""
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import requests
from loguru import logger

from config import load_config

DEFAULT_TIMEOUT = 10
BOOKING_URL = "https://pcticket.chnmuseum.cn/museum-en/#/personal/index"


def notify_available(available: list[dict]) -> None:
    """通知用户哪些日期有可预约余票。available 是 query_remaining() 的过滤结果。"""
    if not available:
        return

    cfg = load_config()
    mode = cfg.get("notifier", "type", fallback="off").strip().lower()

    title = f"国博余票提醒：{len(available)} 天可约"
    body = _build_body(available)

    if mode == "off":
        logger.info(f"通知未开启，{len(available)} 天有余票（仅记录日志）")
        return

    if mode in ("serverchan", "both"):
        _send_serverchan(cfg, title, body)
    if mode in ("email", "both"):
        _send_email(cfg, title, body)


def _build_body(days: list[dict]) -> str:
    lines = ["📅 以下日期有可预约的余票：", ""]
    for d in days:
        lines.append(f"  ✅ {d['date']} - {d['description']}")
    lines += ["", f"👉 立即预约：{BOOKING_URL}"]
    return "\n".join(lines)


def _send_serverchan(cfg, title: str, content: str) -> None:
    """Server酱 微信推送。"""
    sendkey = cfg.get("notifier", "serverchan_sendkey", fallback="").strip()
    if not sendkey:
        logger.warning("Server酱 SendKey 未配置，跳过推送")
        return

    url = f"https://sctapi.ftqq.com/{sendkey}.send"
    try:
        resp = requests.post(url, data={"title": title, "content": content}, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") == 0:
            logger.success("✓ Server酱推送成功")
        else:
            logger.error(f"Server酱推送失败: {result}")
    except Exception as e:
        logger.error(f"Server酱推送异常: {e}")


def _send_email(cfg, title: str, content: str) -> None:
    """邮件通知。QQ 邮箱默认，其他邮箱改 smtp_host。"""
    user = cfg.get("notifier", "smtp_user", fallback="").strip()
    smtp_host = cfg.get("notifier", "smtp_host", fallback="smtp.qq.com")
    smtp_port = cfg.getint("notifier", "smtp_port", fallback=465)
    smtp_pass = cfg.get("notifier", "smtp_pass", fallback="").strip()
    mail_to = cfg.get("notifier", "mail_to", fallback="").strip()

    if not all([user, smtp_pass, mail_to]):
        logger.warning("邮件配置不完整，跳过推送")
        return

    msg = MIMEText(content, "plain", "utf-8")
    msg["Subject"] = Header(title, "utf-8")
    msg["From"] = user
    msg["To"] = mail_to

    try:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=DEFAULT_TIMEOUT) as smtp:
            smtp.login(user, smtp_pass)
            smtp.sendmail(user, [mail_to], msg.as_string())
        logger.success(f"✓ 邮件发送成功 -> {mail_to}")
    except Exception as e:
        logger.error(f"邮件发送失败: {e}")
