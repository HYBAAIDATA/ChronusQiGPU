"""
Benchmark Target 1: search_engine.py
"""
class SearchEngine:
    def __init__(self, index_name: str):
        self.index_name = index_name
        self.documents = []

    def add_document(self, doc_id: int, content: str):
        self.documents.append({"id": doc_id, "content": content})

    def query(self, term: str):
        results = []
        for doc in self.documents:
            if term in doc["content"]:
                results.append(doc)
        return results
