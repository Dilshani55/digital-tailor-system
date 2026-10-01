import os
import sys

from app import create_app

app = create_app()


def _database_label(uri):
    """Host and database name of a MongoDB URI, without any user name or password."""
    rest = uri.split("://", 1)[-1].split("?", 1)[0]
    return rest.split("@", 1)[-1]


if __name__ == "__main__":
    port = os.environ.get("PORT", "5000")
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    print("Starting Digital Tailor API...")
    print("Python:  " + sys.executable + ("" if in_venv else "   (not the project's venv - use start_backend.ps1 or backend\\venv\\Scripts\\python)"))
    print("MongoDB: " + _database_label(app.config["MONGO_URI"]))
    print("API running at: http://127.0.0.1:" + port)
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", port=int(port))
