import hashlib, json

def sha256_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',',':'), ensure_ascii=False, default=list).encode()).hexdigest()
