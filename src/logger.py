
import os
import inspect
from datetime import datetime

# Determine the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

def _write_log(filename, level, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Get caller frame
    frame = inspect.currentframe().f_back.f_back # Go back 2 steps (to caller of log_x)
    if frame:
        file = os.path.basename(frame.f_code.co_filename)
        line = frame.f_lineno
        func = frame.f_code.co_name
    else:
        file = "unknown"
        line = 0
        func = "unknown"
        
    line_txt = f"{timestamp} [{level}] {file}:{line} {func}() | {message}\n"

    with open(os.path.join(LOG_DIR, filename), "a", encoding="utf-8") as f:
        f.write(line_txt)

def log_debug(msg): _write_log("debug.log", "DEBUG", msg)
def log_info(msg):  _write_log("info.log", "INFO", msg)
def log_warn(msg):  _write_log("warn.log", "WARN", msg)
def log_error(msg): _write_log("error.log", "ERROR", msg)

def log_phase(phase_name, variables: dict):
    filename = f"phase_{phase_name}.log"
    with open(os.path.join(LOG_DIR, filename), "a", encoding="utf-8") as f:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"=== PHASE {phase_name} START ===\n")
        f.write(f"timestamp = {now}\n\n")
        for key, value in variables.items():
            f.write(f"{key} = {value}\n")
        f.write("\n")
