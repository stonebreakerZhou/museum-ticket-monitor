"""国博余票查询。基于公开的英文版 API，无需登录。

使用的接口是 /pool/ingore/getCalendar，该接口在 hallTicketPoolVOS 中按展厅
返回真实状态和票数。gainAllSystemConfig 只返回粗粒度状态（"日期在窗口内"），
并不反映真实库存——会被误判为有票。
"""
import re
import time
import requests
from loguru import logger

from config import load_config

CALENDAR_URL = "https://pcticket.chnmuseum.cn/prod-api/pool/ingore/getCalendar"

# status 含义（来自接口实测）：
#  -1: 不可约（闭馆/过期）
#   0: 已满/售罄
#   1: 可预约（今日）
#   3: 可预约（未来日期）
#   4: 受限/维护（具体看 ruleContent / closeContent）
AVAILABLE_STATUSES = (1, 3)

DEFAULT_TIMEOUT = 10
DEFAULT_RETRIES = 2


def _strip_html(text: str) -> str:
    """去除 HTML 标签并压缩空白。"""
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def _request_once(cfg) -> dict | None:
    """单次 API 请求，失败返回 None。"""
    params = {
        "saleMode": 1,
        "hallType": 91,
        "openPerson": 1,
        "channel": cfg.get("museum", "api_channel"),
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://pcticket.chnmuseum.cn/museum-en/",
        "Accept": "application/json, text/plain, */*",
    }
    try:
        resp = requests.get(CALENDAR_URL, params=params, headers=headers, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        logger.warning("API 请求超时")
    except requests.exceptions.SSLError as e:
        logger.warning(f"SSL 错误: {e}")
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else "?"
        logger.warning(f"HTTP 状态码异常: {code}")
    except requests.exceptions.RequestException as e:
        logger.warning(f"网络错误: {e}")
    except ValueError as e:
        logger.warning(f"响应不是合法 JSON: {e}")
    return None


def _resolve_hall(date_entry: dict, hall_id: int) -> dict | None:
    """从某日期的 hallTicketPoolVOS 中找出指定 hall_id 的子项。"""
    per_hall = date_entry.get("hallTicketPoolVOS") or []
    for h in per_hall:
        if h.get("hallId") == hall_id:
            return h
    return None


def _describe(hall_info: dict | None, top_status: int) -> tuple[int, int, bool, str]:
    """返回 (status, ticket_pool, available, description)。"""
    if hall_info is None:
        pool = 0
        status = top_status
    else:
        pool = hall_info.get("ticketPool", 0) or 0
        status = hall_info.get("status", top_status)

    available = status in AVAILABLE_STATUSES and pool > 0

    if available:
        description = "可预约"
    elif status == 0 or (status in AVAILABLE_STATUSES and pool == 0):
        reason = _strip_html((hall_info or {}).get("ruleContent", ""))
        description = reason or "已满/售罄"
    elif status == 4:
        reason = _strip_html((hall_info or {}).get("ruleContent", "")) \
                 or _strip_html((hall_info or {}).get("closeContent", ""))
        description = reason or "受限/维护"
    elif status == -1:
        reason = _strip_html((hall_info or {}).get("closeContent", ""))
        description = reason or "不可约"
    else:
        description = f"未知状态({status})"

    return status, pool, available, description


def query_remaining(hall_id: int = 1, retries: int = DEFAULT_RETRIES) -> list[dict]:
    """查询未来 14 天余票，失败按指数退避重试。

    参数:
        hall_id: 展厅 ID。1 = 基本陈列（免费），750 = 庞贝特展（付费）

    返回的每条记录字段:
        date, status, ticket_pool, available, description, today
    """
    cfg = load_config()
    payload = None
    for attempt in range(1, retries + 2):
        payload = _request_once(cfg)
        if payload is not None:
            break
        if attempt <= retries:
            wait = 2 ** attempt
            logger.info(f"第 {attempt} 次失败，{wait} 秒后重试")
            time.sleep(wait)

    if payload is None:
        logger.error(f"连续 {retries + 1} 次查询失败，请检查网络或 API 状态")
        return []

    if payload.get("code") != 200:
        logger.error(f"API 返回错误: {payload.get('msg', '未知错误')}")
        return []

    days = payload.get("data", [])
    results = []
    for d in days:
        hall_info = _resolve_hall(d, hall_id)
        status, pool, available, description = _describe(hall_info, d.get("status", -1))
        results.append({
            "date": d.get("currentDate", ""),
            "status": status,
            "ticket_pool": pool,
            "available": available,
            "description": description,
            "today": d.get("today", 0) == 1,
        })
    return results


if __name__ == "__main__":
    print("=" * 60)
    print("国博余票查询 - 单次测试")
    print("=" * 60)
    results = query_remaining(hall_id=1)
    if results:
        print(f"\n查询到 {len(results)} 天的余票信息：\n")
        for r in results:
            mark = "[OK]" if r["available"] else "[NO]"
            print(f"  {mark} {r['date']} - {r['description']} "
                  f"(status={r['status']}, pool={r['ticket_pool']}, today={r['today']})")
    else:
        print("\n查询失败，请检查网络或 API 配置")