from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models import School, User
from app.services.excel_service import ExcelService


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        school = School(name="Demo School")
        db.add(school)
        db.flush()
        db.add(User(school_id=school.id, email="admin@example.com", full_name="Admin User", password_hash=hash_password("password123")))
        stream = ExcelService(db).build_template()
        batch, errors = ExcelService(db).import_workbook(school.id, "demo_template.xlsx", stream.getvalue())
        print({"school_id": school.id, "batch_status": batch.status, "errors": [e.__dict__ for e in errors]})
    finally:
        db.close()


if __name__ == "__main__":
    main()
