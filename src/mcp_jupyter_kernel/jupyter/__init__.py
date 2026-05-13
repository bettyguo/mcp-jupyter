"""Transport implementations: server-mode REST/WS + standalone-mode kernel subprocess.

Both expose a common KernelSession interface (see session.py) so the tool layer
above doesn't care which mode it's in.
"""
