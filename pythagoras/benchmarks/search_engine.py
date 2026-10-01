"""PYTHAGORAS v12 benchmark target: in-memory search engine."""


class SearchEngine:
    def __init__(self, index_name: str):
        self.index_name = index_name
        self.documents = []

    def add_document(self, doc_id: int, content: str):
        self.documents.append({"id": doc_id, "content": content})

    def query(self, term: str):
        results = []
        for document in self.documents:
            if term in document["content"]:
                results.append(document)
        return results
