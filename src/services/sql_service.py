import os
from contextlib import closing
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor


class SqlService:
    def __init__(self, dsn: Optional[str] = None) -> None:
        self.dsn = dsn or self._build_dsn_from_env()
        self._ensure_tables()

    def _build_dsn_from_env(self) -> str:
        host = os.getenv("PGHOST", "localhost")
        port = os.getenv("PGPORT", "5432")
        database = os.getenv("PGDATABASE", "postgres")
        user = os.getenv("PGUSER", "postgres")
        password = os.getenv("PGPASSWORD", "postgres")

        return (
            f"host={host} port={port} dbname={database} user={user} password={password}"
        )

    def _get_connection(self):
        return psycopg2.connect(self.dsn)

    def _ensure_tables(self) -> None:
        queries = [
            """
            CREATE TABLE IF NOT EXISTS repository (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS pull_request (
                id SERIAL PRIMARY KEY,
                github_pull_request_id BIGINT NOT NULL UNIQUE,
                pr_type TEXT NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS repository_pull_request (
                repository_id INTEGER NOT NULL REFERENCES repository(id) ON DELETE CASCADE,
                pull_request_id INTEGER NOT NULL REFERENCES pull_request(id) ON DELETE CASCADE,
                PRIMARY KEY (repository_id, pull_request_id)
            );
            """,
        ]

        with closing(self._get_connection()) as connection:
            with closing(connection.cursor()) as cursor:
                for query in queries:
                    cursor.execute(query)
                connection.commit()

    def save_pull_request_mapping(
        self,
        repository_name: str,
        github_pull_request_id: int,
        pr_type: str,
    ) -> Dict[str, int | str]:
        with closing(self._get_connection()) as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(
                    """
                    INSERT INTO repository (name)
                    VALUES (%s)
                    ON CONFLICT (name)
                    DO UPDATE SET name = EXCLUDED.name
                    RETURNING id
                    """,
                    (repository_name,),
                )
                repository_id = cursor.fetchone()[0]

                cursor.execute(
                    """
                    INSERT INTO pull_request (github_pull_request_id, pr_type)
                    VALUES (%s, %s)
                    ON CONFLICT (github_pull_request_id)
                    DO UPDATE SET pr_type = EXCLUDED.pr_type
                    RETURNING id
                    """,
                    (github_pull_request_id, pr_type),
                )
                pull_request_id = cursor.fetchone()[0]

                cursor.execute(
                    """
                    INSERT INTO repository_pull_request (repository_id, pull_request_id)
                    VALUES (%s, %s)
                    ON CONFLICT (repository_id, pull_request_id)
                    DO NOTHING
                    """,
                    (repository_id, pull_request_id),
                )
                connection.commit()

        return {
            "repository_id": repository_id,
            "pull_request_id": pull_request_id,
            "github_pull_request_id": github_pull_request_id,
            "pr_type": pr_type,
        }

    def get_all(self) -> List[Dict[str, Any]]:
        query = """
            SELECT
                rp.repository_id,
                r.name AS repository_name,
                rp.pull_request_id,
                p.github_pull_request_id,
                p.pr_type
            FROM repository_pull_request rp
            JOIN repository r ON r.id = rp.repository_id
            JOIN pull_request p ON p.id = rp.pull_request_id
            ORDER BY rp.repository_id ASC, rp.pull_request_id ASC
        """

        with closing(self._get_connection()) as connection:
            with closing(connection.cursor(cursor_factory=RealDictCursor)) as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]

