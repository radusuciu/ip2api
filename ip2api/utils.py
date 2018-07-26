"""Utility methods."""
import hashlib

def equal_dicts(a, b, ignore_keys):
    """Compare two dicts, withholding a set of keys.

    From: http://stackoverflow.com/a/10480904/383744
    """
    ka = set(a).difference(ignore_keys)
    kb = set(b).difference(ignore_keys)
    return ka == kb and all(a[k] == b[k] for k in ka)


def file_md5(fname):
    """Get md5 hash for a file.

    From: https://stackoverflow.com/a/3431838/383744
    """
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def read_in_chunks(f, chunk_size=51200000):
    """Read file in 50 MB (default) chunks)."""
    while True:
        data = f.read(chunk_size)
        if not data:
            break
        yield data
