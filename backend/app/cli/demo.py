"""`dss seed-demo`: an analyst with an imported dataset and a report, ready for any client.

Running it again reuses what exists (the account, the same file, its report).
"""

import hashlib
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.cli.jobs import run_job
from app.core.config import Settings
from app.ingest import reader
from app.models import Analyst, Dataset, Job, Report
from app.services import auth, datasets, jobs, reports


@dataclass(frozen=True)
class DemoResult:
    email: str
    analyst_created: bool
    dataset_id: int
    dataset_status: str
    dataset_created: bool
    report_id: int | None


def simulate(preset: str, seed: int, users: int | None, months: int | None) -> tuple[str, bytes]:
    """A libsim dataset as (file name, bytes), the same file `libsim generate` writes.

    libsim is a dev dependency, so this raises ImportError in the production image.
    """
    from libsim import engine, writer
    from libsim.params import preset as make_params

    overrides: dict[str, Any] = {"seed": seed}
    if users:
        overrides["users"] = users
    if months:
        overrides["months"] = months
    result = engine.simulate(make_params(preset, **overrides))
    with tempfile.TemporaryDirectory() as folder:
        dataset, _ = writer.write(result, Path(folder))
        return dataset.name, dataset.read_bytes()


def _import(session_factory: jobs.SessionFactory, dataset_id: int) -> str:
    """Run the dataset's pending import here, or wait for the worker that took it."""
    with session_factory() as session:
        job = session.scalars(
            select(Job).where(Job.dataset_id == dataset_id).order_by(Job.created_at.desc())
        ).first()
    if job is not None and job.status not in jobs.TERMINAL:
        run_job(session_factory, job.id)
    with session_factory() as session:
        return session.get_one(Dataset, dataset_id).status


def seed_demo(
    session_factory: jobs.SessionFactory,
    settings: Settings,
    *,
    email: str,
    name: str,
    password: str,
    filename: str,
    content: bytes,
    dataset_name: str,
) -> DemoResult:
    with session_factory() as session:
        analyst = session.scalar(
            select(Analyst).where(Analyst.email == auth.normalize_email(email))
        )
        analyst_created = analyst is None
        if analyst is None:
            analyst = auth.create_analyst(session, email=email, name=name, password=password)
        digest = hashlib.sha256(reader.decompress(content)).hexdigest()
        dataset = session.scalar(
            select(Dataset).where(Dataset.owner_id == analyst.id, Dataset.sha256 == digest)
        )
        dataset_created = dataset is None
        if dataset is None:
            dataset, _ = datasets.create_from_upload(
                session, settings, analyst, filename=filename, content=content, name=dataset_name
            )
        dataset_id = dataset.id

    status = _import(session_factory, dataset_id)
    report_id = None
    if status == "ready":
        with session_factory() as session:
            analyst = session.get_one(Analyst, analyst.id)
            report_id = session.scalar(
                select(Report.id).where(Report.dataset_id == dataset_id).order_by(Report.id)
            )
            if report_id is None:
                title = f"Демо-звіт: {dataset_name}"
                report_id = reports.create(session, analyst, dataset_id=dataset_id, title=title).id
    return DemoResult(
        email=analyst.email,
        analyst_created=analyst_created,
        dataset_id=dataset_id,
        dataset_status=status,
        dataset_created=dataset_created,
        report_id=report_id,
    )
