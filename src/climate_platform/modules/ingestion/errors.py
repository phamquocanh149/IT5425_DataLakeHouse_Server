"""Ingestion domain errors: rejections raised by the non-HTTP ingestion collaborators."""


class IngestionError(Exception):
    """An upload the ingestion pipeline rejects (mapped to HTTP by the controller)."""

    def __init__(self, status, detail):
        super().__init__(detail)
        self.status = status
        self.detail = detail
