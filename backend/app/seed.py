"""Insert one reproducible sample run into an empty database."""
from sqlalchemy import select

from .db import SessionLocal
from .models import Run
from .search import Settings
from .service import create_run


def main() -> None:
    with SessionLocal() as session:
        if session.scalar(select(Run.id).limit(1)) is None:
            demo = create_run(session, Settings(seed=42, machines=4, job_count=24,
                                                case_count=8, candidate_limit=500, holdout_count=4))
            print(f"Created demo run {demo.id}")
        else:
            print("Demo seed skipped: existing runs found")


if __name__ == "__main__":
    main()
