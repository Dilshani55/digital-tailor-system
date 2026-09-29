import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    print("Starting Digital Tailor API...")
    print("MongoDB: digital_tailor_db @ localhost:27017")
    print("API running at: http://127.0.0.1:5000")
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", port=5000)
