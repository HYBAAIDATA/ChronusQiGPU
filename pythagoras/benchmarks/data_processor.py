"""PYTHAGORAS v12 benchmark target: data processor."""


class DataProcessor:
    def process_records(self, records):
        out = []
        for record in records:
            value = record * 2.0
            out.append(value)
        return out
