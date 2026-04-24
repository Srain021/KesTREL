"""Alembic migration root.

Generate the initial baseline:
    alembic -c alembic.ini revision --autogenerate -m "initial schema"

Apply:
    alembic -c alembic.ini upgrade head

Override target DB:
    KESTREL_DB_URL=sqlite:///~/.kestrel/engagements/foo/engagement.db alembic upgrade head
"""
