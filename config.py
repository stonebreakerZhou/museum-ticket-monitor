"""配置加载。"""
from pathlib import Path
import configparser
from loguru import logger

CONFIG_PATH = Path("config.ini")


def load_config(path: Path = CONFIG_PATH) -> configparser.ConfigParser:
    """加载配置文件。

    文件不存在时记录错误并抛出 FileNotFoundError，由调用方决定如何退出。
    """
    if not path.exists():
        logger.error(f"配置文件不存在: {path}")
        logger.error("请先复制 config.ini.example 为 config.ini 后再运行")
        raise FileNotFoundError(path)
    cfg = configparser.ConfigParser()
    cfg.read(path, encoding="utf-8")
    return cfg
