import sys

from app.routes import app, configure_db
from db.access import init_db

DB_PATH = "itr2_rsu_assistant.db"


def main():
    init_db(DB_PATH)
    configure_db(DB_PATH)
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
