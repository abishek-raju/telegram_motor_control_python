import time
from src.utils import pylogger, rich_utils


log = pylogger.get_pylogger(__name__)

def hello_world():
    print("Hello World")
    time.sleep(1)
    log.info("Running Function")