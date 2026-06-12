# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

from contextlib import contextmanager

from sqlalchemy import event

from system.db.database import db


@contextmanager
def assert_max_queries(max_count: int, label: str = ""):
    """Assert that at most `max_count` SQL queries execute within the block.

    Usage:
        with assert_max_queries(6, "dashboard index"):
            response = client.get("/")
            assert response.status_code == 200
    """
    count = 0
    stmts: list[str] = []

    def _after_execute(conn, cursor, statement, parameters, context, executemany):
        nonlocal count
        count += 1
        stmts.append(statement[:120])

    engine = db.engine
    event.listen(engine, "after_cursor_execute", _after_execute)
    try:
        yield
    finally:
        event.remove(engine, "after_cursor_execute", _after_execute)

    if count > max_count:
        detail = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(stmts))
        tag = f" [{label}]" if label else ""
        raise AssertionError(
            f"Query budget exceeded{tag}: {count} queries (max {max_count})\n{detail}"
        )
