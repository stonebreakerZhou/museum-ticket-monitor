"""国博余票查询。基于公开的英文版 API，无需登录。"""
import time
import requests
from loguru import logger

from config import load_config

STATUS_DESCRIPTION = {
    -1: "不可约（闭馆/过期）",
    0: "已满/售罄",
    1: "可预约（今日）",
    3: "可预约（未来日期）",
    4: "维护中",
}

DEFAULT_TIMEOUT = 10
DEFAULT_RETRIES = 2
AVAILABLE_STATUSES = (1, 3)


def _request_once(cfg) -> dict | None:
    """单次 API 请求，失败返回 None。"""
    url = cfg.get("museum", "api_url")
    params = {
        "channel": cfg.get("museum", "api_channel"),
        "ticketUseType": cfg.getint("museum", "api_ticket_use_type"),
        "personType": cfg.getint("museum", "api_person_type"),
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://pcticket.chnmuseum.cn/museum-en/",
        "Accept": "application/json, text/plain, */*",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=DEFAULT_TIMEOUT)
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


def query_remaining(retries: int = DEFAULT_RETRIES) -> list[dict]:
    """查询未来 14 天余票，失败按指数退避重试。

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

    days = payload.get("data", {}).get("calendarTicketPoolsByDate", [])
    return [
        {
            "date": d.get("currentDate", ""),
            "status": d.get("status", -1),
            "ticket_pool": d.get("ticketPool", 0),
            "available": d.get("status") in AVAILABLE_STATUSES,
            "description": STATUS_DESCRIPTION.get(d.get("status", -1), f"未知状态({d.get('status')})"),
            "today": d.get("today", 0) == 1,
        }
        for d in days
    ]


if __name__ == "__main__":
    print("=" * 60)
    print("国博余票查询 - 单次测试")
    print("=" * 60)
    results = query_remaining()
    if results:
        print(f"\n查询到 {len(results)} 天的余票信息：\n")
        for r in results:
            mark = "[OK]" if r["available"] else "[NO]"
            print(f"  {mark} {r['date']} - {r['description']} (pool={r['ticket_pool']}, today={r['today']})")
    else:
        print("\n查询失败，请检查网络或 API 配置")
