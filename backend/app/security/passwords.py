import hashlib
import hmac
import os

# scrypt parameters: about 16 MB of memory per hash, fine for a small VM
N, R, P = 2**14, 8, 1
KEY_LENGTH = 32


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=N, r=R, p=P, dklen=KEY_LENGTH)
    return f"scrypt${N}${R}${P}${salt.hex()}${key.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, key_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = bytes.fromhex(key_hex)
        key = hashlib.scrypt(
            password.encode(),
            salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p),
            dklen=len(expected),
        )
        return hmac.compare_digest(key, expected)
    except (ValueError, TypeError):
        return False


# Used to spend the same time when a username does not exist
DUMMY_HASH = hash_password("not-a-real-password")
