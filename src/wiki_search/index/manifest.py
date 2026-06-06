from ..db.repository import DocumentRepository


class Manifest:
    def __init__(self, doc_repo: DocumentRepository):
        self.doc_repo = doc_repo

    def has_changed(self, path: str, content_hash: str) -> bool:
        doc = self.doc_repo.get_document_by_path(path)
        if doc is None:
            return True
        return doc["hash"] != content_hash

    def is_indexed(self, path: str) -> bool:
        return self.doc_repo.get_document_by_path(path) is not None
