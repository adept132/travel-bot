import subprocess
import sys
import time


def main():
    print("🚀 Starting both services...")

    health_process = subprocess.Popen([sys.executable, "health.py"])

    time.sleep(3)

    try:
        subprocess.run([sys.executable, "fly_polling.py"], check=True)
    except KeyboardInterrupt:
        pass
    finally:
        health_process.terminate()


if __name__ == "__main__":
    main()