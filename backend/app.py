from __future__ import annotations

from flask import Flask, jsonify, request
from flask_cors import CORS

from .runtime import Runtime

app = Flask(__name__)
CORS(app)


@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "message": "Pynescript Server is running. Send POST requests to /run."})


@app.route("/run", methods=["POST"])
def run_pine_script():
    data = request.get_json()
    pine_script = data.get("script", "")
    ohlcv_data = data.get("data", [])

    if not pine_script:
        return jsonify({"status": "error", "message": "No script provided"}), 400

    if not ohlcv_data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    runtime = Runtime()
    result = runtime.run(pine_script, ohlcv_data)

    if "error" in result:
        return jsonify({"status": "error", "message": result["error"]}), 500

    response_data = {"status": "success", "message": "Script executed successfully", "data": result["plots"]}

    return jsonify(response_data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
