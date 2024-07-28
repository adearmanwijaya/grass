import sys
import re
from loguru import logger

def logging_setup():
    format_info = "<green>{time:HH:mm:ss.SS}</green> <blue>{level}</blue> <level>{message}</level>"

    logger.remove()  # Menghapus semua handler default

    # Hanya menambahkan handler stdout untuk logging ke console
    logger.add(sys.stdout, format=format_info, level="INFO", colorize=True)


def clean_brackets(raw_str):
    clean_text = re.sub(brackets_regex, '', raw_str)
    return clean_text

brackets_regex = re.compile(r'<.*?>')

logging_setup()