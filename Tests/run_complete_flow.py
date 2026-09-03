import subprocess
import time
import sys
import os

def main():
    print("=== STARTING SERVER SUBPROCESS ===")
    env = os.environ.copy()
    # Ensure stdout/stderr are unbuffered so we capture logs immediately
    env["PYTHONUNBUFFERED"] = "1"
    
    server_proc = subprocess.Popen(
        [sys.executable, "API/main.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        text=True
    )
    
    # Wait for server to bind and start
    time.sleep(4)
    
    print("=== EXECUTING TEST COMPLETE VALIDATION ===")
    try:
        # Run test_complete_validation.py in another subprocess
        val_proc = subprocess.run(
            [sys.executable, "Tests/test_complete_validation.py"],
            capture_output=True,
            text=True
        )
        print("Validation stdout:")
        print(val_proc.stdout)
        if val_proc.stderr:
            print("Validation stderr:")
            print(val_proc.stderr)
    except Exception as e:
        print(f"Error running test_complete_validation.py: {e}")

    print("=== EXECUTING TEST API SAVE ===")
    try:
        # Run test_api_save.py in another subprocess
        save_proc = subprocess.run(
            [sys.executable, "Tests/test_api_save.py"],
            capture_output=True,
            text=True
        )
        print("API save stdout:")
        print(save_proc.stdout)
        if save_proc.stderr:
            print("API save stderr:")
            print(save_proc.stderr)
    except Exception as e:
        print(f"Error running test_api_save.py: {e}")

    print("=== STOPPING SERVER SUBPROCESS ===")
    server_proc.terminate()
    try:
        server_out, _ = server_proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        server_proc.kill()
        server_out, _ = server_proc.communicate()

    print("=== SERVER LOGS INSPECTION ===")
    warning_found = False
    for line in server_out.splitlines():
        if "Skipping data after last boundary" in line:
            warning_found = True
            print(f"[FOUND WARNING] {line}")
        elif "INFO:" in line or "WARNING:" in line or "ERROR:" in line:
            # Print other log lines for sanity
            print(line)
            
    print("================================")
    if warning_found:
        print("RESULT: Warning 'Skipping data after last boundary' WAS DETECTED.")
    else:
        print("RESULT: Warning 'Skipping data after last boundary' WAS NOT DETECTED! (FIXED)")
    print("================================")

if __name__ == "__main__":
    main()
