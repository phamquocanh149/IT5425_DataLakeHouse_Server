"""SQLAlchemy grants repository (``control.sqlite3``).

Every statement is an ORM construct (``select``/``insert``/``delete``); the SQLite upsert
keeps the previous ``INSERT OR REPLACE`` semantics for the ``(user_id, dataset_id, layer)``
primary key.
"""

import json

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from climate_platform.entity import control as _control  # noqa: F401  (populate metadata)
from climate_platform.entity.control import Grant


class GrantRepository:
    def __init__(self, store):
        self.store = store

    def actions(self, uid, dataset):
        with self.store.db() as db:
            rows = (
                db.execute(
                    select(Grant.layer, Grant.actions).where(
                        Grant.user_id == uid, Grant.dataset_id == dataset
                    )
                )
                .mappings()
                .all()
            )
        return {r["layer"]: json.loads(r["actions"]) for r in rows}

    def actions_by_dataset(self, uid):
        """All grants of ``uid`` in one query as ``{dataset_id: {layer: [actions]}}``.

        Lets catalog listings resolve visibility once instead of one query per dataset.
        """
        with self.store.db() as db:
            rows = (
                db.execute(
                    select(Grant.dataset_id, Grant.layer, Grant.actions).where(Grant.user_id == uid)
                )
                .mappings()
                .all()
            )
        result = {}
        for row in rows:
            result.setdefault(row["dataset_id"], {})[row["layer"]] = json.loads(row["actions"])
        return result

    def get(self, db, target, dataset_id, layer):
        return (
            db.execute(
                select(Grant).where(
                    Grant.user_id == target,
                    Grant.dataset_id == dataset_id,
                    Grant.layer == layer,
                )
            )
            .mappings()
            .first()
        )

    def upsert(self, db, target, dataset_id, layer, actions, version):
        normalized = json.dumps(sorted(set(actions)))
        db.execute(
            sqlite_insert(Grant)
            .values(
                user_id=target,
                dataset_id=dataset_id,
                layer=layer,
                actions=normalized,
                version=version,
            )
            .on_conflict_do_update(
                index_elements=[Grant.user_id, Grant.dataset_id, Grant.layer],
                set_={"actions": normalized, "version": version},
            )
        )

    def delete(self, db, target, dataset_id, layer):
        db.execute(
            delete(Grant).where(
                Grant.user_id == target,
                Grant.dataset_id == dataset_id,
                Grant.layer == layer,
            )
        )

    def list_for_user(self, db, target):
        rows = (
            db.execute(
                select(Grant).where(Grant.user_id == target).order_by(Grant.dataset_id, Grant.layer)
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    def for_user(self, target):
        with self.store.db() as db:
            return self.list_for_user(db, target)
