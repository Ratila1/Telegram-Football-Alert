from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Football Alert Bot работает 24/7"

def keep_alive():
    t = Thread(target=lambda: app.run(host='0.0.0.0', port=8080))
    t.start()