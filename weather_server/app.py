"""
Weather Station Flask Server
- Receives POST from ESP32 at /api/reading
- Serves JSON at /api for BJJ Gym Timer
- Serves HTML at / for browser
"""

from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)

# Store latest readings from ESP32
temperature = 0.0
humidity = 0.0


@app.route("/api/reading", methods=["POST"])
def api_reading():
    """Receive temp/humidity from ESP32."""
    global temperature, humidity
    try:
        data = request.get_json()
        if data:
            temperature = float(data.get("temp", temperature))
            humidity = float(data.get("humidity", humidity))
        return jsonify({"ok": True}), 200
    except Exception:
        return jsonify({"ok": False}), 400


@app.route("/api")
def api():
    """Return JSON for BJJ Gym Timer (and other clients)."""
    return jsonify({
        "temperature": temperature,
        "temp": temperature,
        "humidity": humidity,
    })


@app.route("/")
def index():
    """Serve HTML page."""
    return render_template_string(HTML_TEMPLATE, temp=temperature, hum=humidity)


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="refresh" content="5">
  <title>Weather Station</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Segoe UI', system-ui, sans-serif;
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #eee;
    }
    .card {
      background: rgba(255,255,255,0.08);
      border-radius: 16px;
      padding: 2rem;
      text-align: center;
      box-shadow: 0 8px 32px rgba(0,0,0,0.3);
      border: 1px solid rgba(255,255,255,0.1);
    }
    h1 { font-size: 1.5rem; margin-bottom: 1.5rem; color: #a8dadc; }
    .reading { font-size: 3rem; font-weight: 700; margin: 0.5rem 0; }
    .label { font-size: 0.9rem; opacity: 0.8; }
    .temp { color: #e07a5f; }
    .humidity { color: #81b29a; }
    .refresh { font-size: 0.75rem; margin-top: 1rem; opacity: 0.6; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Weather Station</h1>
    <div class="label">Temperature</div>
    <div class="reading temp">{{ temp }}&deg;C</div>
    <div class="label">Humidity</div>
    <div class="reading humidity">{{ hum }}%</div>
    <div class="refresh">Auto-refresh every 5 seconds</div>
  </div>
</body>
</html>
"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
