import logging

logger = logging.getLogger("ai-reviewer")
handler = logging.StreamHandler()
fmt = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
handler.setFormatter(fmt)
logger.addHandler(handler)
logger.setLevel(logging.INFO)
