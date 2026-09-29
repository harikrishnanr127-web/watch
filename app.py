import os

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from google import genai
from google.genai import types

import chatbot_config as cfg

load_dotenv()

app = Flask(__name__)

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", cfg.MODEL_NAME)
client = genai.Client(api_key=API_KEY) if API_KEY else None


def build_contents(history, message):
    """Turn the chat history sent by the browser into Gemini `Content` objects."""
    contents = []
    if isinstance(history, list):
        for turn in history[-cfg.MAX_HISTORY_TURNS:]:
            if not isinstance(turn, dict):
                continue
            role = "user" if turn.get("role") == "user" else "model"
            text = str(turn.get("text", "")).strip()[: cfg.MAX_MESSAGE_CHARS]
            if text:
                contents.append(types.Content(role=role, parts=[types.Part(text=text)]))
    contents.append(types.Content(role="user", parts=[types.Part(text=message)]))
    return contents


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    if client is None:
        return jsonify(error="GEMINI_API_KEY is missing. Add it to your .env file."), 500

    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()

    if not message:
        return jsonify(error="Type a question first."), 400
    if len(message) > cfg.MAX_MESSAGE_CHARS:
        return jsonify(error=f"Keep messages under {cfg.MAX_MESSAGE_CHARS} characters."), 400

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=build_contents(data.get("history"), message),
            config=types.GenerateContentConfig(
                system_instruction=cfg.SYSTEM_PROMPT,
                temperature=cfg.TEMPERATURE,
                max_output_tokens=cfg.MAX_OUTPUT_TOKENS,
            ),
        )
        reply = (response.text or "").strip() or cfg.OFF_TOPIC_REPLY
        return jsonify(reply=reply)
    except Exception as exc:  # network errors, quota, invalid key, etc.
        app.logger.exception("Gemini request failed: %s", exc)
        return jsonify(error="WATCHBOT couldn't reach Gemini. Check your API key and try again."), 502


@app.route("/health")
def health():
    return jsonify(status="ok", model=MODEL)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=os.getenv("FLASK_DEBUG") == "1")
