import os
import subprocess
import datetime

log_file = "/Users/naveenchawla/Repos/google_adk_voice_bot/check.log"

with open(log_file, "w") as f:
    f.write(f"Diagnostic started at {datetime.datetime.now()}\n")
    
    try:
        df = subprocess.check_output(["df", "-h", "."]).decode()
        f.write("--- DF ---\n" + df + "\n")
    except Exception as e:
        f.write(f"DF Failed: {e}\n")
        
    try:
        ps = subprocess.check_output(["ps", "aux"]).decode()
        # Filter for app.py
        app_ps = "\n".join([line for line in ps.split("\n") if "app.py" in line])
        f.write("--- PS APP.PY ---\n" + app_ps + "\n")
    except Exception as e:
        f.write(f"PS Failed: {e}\n")

    f.write("Diagnostic finished.\n")
