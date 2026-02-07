"""
Decorators utilities
"""

import sys
import time
from functools import wraps

def timed(fn):
    """Used to profile and measure processing time of the function it decorates"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = fn(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"{fn.__name__} took {elapsed:.3f}s", file=sys.stderr)
        return result
    return wrapper
