"""Flask integration example for sesmio.

Install:
    pip install sesmio[flask]

Run:
    AWS_DEFAULT_REGION=us-east-1 SESMIO_DEFAULT_FROM=no-reply@example.com flask --app flask_app run
"""

from __future__ import annotations

from flask import Flask, request

from sesmio.integrations.flask import SESExtension

# Option A: direct init -------------------------------------------------------
app = Flask(__name__)
ses = SESExtension(app, default_from="no-reply@example.com")

# Option B: application factory -----------------------------------------------
# ses = SESExtension()
#
# def create_app():
#     app = Flask(__name__)
#     app.config["SESMIO_REGION"] = "us-east-1"
#     app.config["SESMIO_DEFAULT_FROM"] = "no-reply@example.com"
#     ses.init_app(app)
#     return app


@app.route("/signup", methods=["POST"])
def signup() -> tuple[dict[str, str], int]:
    data = request.get_json(silent=True) or {}
    email = data.get("email", "user@example.com")

    msg_id = ses.send(
        to=email,
        subject="Welcome to our app!",
        html="<h1>Welcome!</h1><p>Thanks for signing up.</p>",
        text="Welcome! Thanks for signing up.",
    )
    return {"message_id": msg_id}, 200


if __name__ == "__main__":
    app.run(debug=True)
