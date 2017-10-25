from simple_imagine.base import db

from  simple_imagine.app import create_app


def init_db():


    app = create_app()


    with app.app_context():
        db.drop_all()
        db.create_all()

if __name__ == "__main__":
    init_db()
