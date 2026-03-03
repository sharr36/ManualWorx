"""arq worker entry point."""

from arq.connections import RedisSettings

from .config import WorkerSettings as Config
from .tasks.annotate_diagram import annotate_diagram
from .tasks.classify_pages import classify_pages
from .tasks.generate_embeddings import generate_embeddings
from .tasks.generate_learning_path import generate_learning_path
from .tasks.ingest_manual import ingest_manual
from .tasks.process_page import process_page

_config = Config()


class WorkerSettings:
    """arq worker settings."""

    functions = [
        ingest_manual,
        process_page,
        generate_embeddings,
        classify_pages,
        annotate_diagram,
        generate_learning_path,
    ]

    redis_settings = RedisSettings.from_dsn(_config.REDIS_URL)

    max_jobs = 10
    job_timeout = 600  # 10 minutes per job
    keep_result = 3600  # Keep results for 1 hour
