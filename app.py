from flask import Flask, jsonify
from flask_cors import CORS
from config import Config

app = Flask(__name__, static_folder="static", static_url_path="/")
CORS(app)

app.config.from_object(Config)


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"})


@app.route("/api/generate", methods=["POST"])
def generate():
    # We will implement this later
    return jsonify({"message": "Generation endpoint ready"})


if __name__ == "__main__":
    app.run(debug=True)