from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Football Alert Bot работает 24/7"

def keep_alive():
    def run():
        print("[FLASK] Starting keep-alive webserver...")
        try:
            app.run(host='0.0.0.0', port=8080)
        except Exception as e:
            print(f"[FLASK ERROR] {e}")

    t = Thread(target=run)
    t.daemon = True
    t.start()
    print("[FLASK] Thread started OK")

