import logging
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

def get_logger(module_name: str):
    logger = logging.getLogger(module_name)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        # file handler
        file_path = LOG_DIR / f"{module_name}.log"
        fh = logging.FileHandler(file_path, mode="a")
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(fh)

        # console handler 
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
        logger.addHandler(ch)

    return logger
