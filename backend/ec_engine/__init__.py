# ec_engine/__init__.py
from .rs_systematic import encode as rs_encode, decode as rs_decode
from .ec_error import ECError

__all__ = ['rs_encode', 'rs_decode', 'ECError']