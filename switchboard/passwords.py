import base64
import hashlib
import hmac
import os

N, R, P = 2 ** 14, 8, 1

def _scrypt(password, salt, n, r, p):
    return hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p,
                          maxmem=64 * 1024 * 1024, dklen=32)

def hash_password(password):
    salt = os.urandom(16)
    digest = _scrypt(password, salt, N, R, P)
    return "scrypt${}${}${}${}${}".format(
        N, R, P, base64.b64encode(salt).decode(), base64.b64encode(digest).decode())

def verify_password(password, stored):
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = _scrypt(password, base64.b64decode(salt), int(n), int(r), int(p))
    except ValueError:
        return False
    return hmac.compare_digest(actual, expected)