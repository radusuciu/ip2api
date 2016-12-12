"""Utility methods."""


def equal_dicts(a, b, ignore_keys):
    """Compare two dicts, withholding a set of keys.

    From: http://stackoverflow.com/a/10480904/383744
    """
    ka = set(a).difference(ignore_keys)
    kb = set(b).difference(ignore_keys)
    return ka == kb and all(a[k] == b[k] for k in ka)
