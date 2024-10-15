import os
import sys
import hashlib
import getpass

try:
    from . import aesctr
except:
    import aesctr


def get_key(passwd, confirm):
    if not passwd:
        while True:
            passwd = getpass.getpass("Enter password: ")
            if not confirm:
                break
            pwconf = getpass.getpass("Confirm password: ")
            if passwd == pwconf:
                break
            print("Passwords are not equal", file=sys.stderr)

    h = hashlib.sha256()
    h.update(passwd.encode('utf-8'))
    return h.digest()

NONCE_SIZE = 16


def validate_ciphertext(aes, in_file):
    # Read encrypted nonce.
    cipher_nonce = in_file.read(NONCE_SIZE)
    if len(cipher_nonce) != NONCE_SIZE:
        return "input too short"

    # Read encrypted hash.
    h = hashlib.md5()
    cipher_hash = in_file.read(h.digest_size)
    if len(cipher_hash) != h.digest_size:
        return "input too short"

    # Compute hash of decrypted nonce.
    h.update(aes.decrypt(cipher_nonce))

    # Check that computed hash matches included hash.
    if h.digest() != aes.decrypt(cipher_hash):
        return "bad password"

    return None


def get_nonce():
    return os.urandom(NONCE_SIZE)


def _do_crypto(aes, in_file, out_file):
    BLOCKSIZE = 65536
    buf = in_file.read(BLOCKSIZE)
    while buf:
        out_file.write(aes.encrypt(buf))
        buf = in_file.read(BLOCKSIZE)


def encrypt(passwd, in_file, out_file):
    aes = aesctr.AESCTRMode(get_key(passwd, True))

    # Write encrypted nonce and hash.
    nonce = get_nonce()
    h = hashlib.md5()
    h.update(nonce)
    out_file.write(aes.encrypt(nonce))
    out_file.write(aes.encrypt(h.digest()))

    # Write rest of encrypted data.
    _do_crypto(aes, in_file, out_file)


def decrypt(passwd, in_file, out_file):
    aes = aesctr.AESCTRMode(get_key(passwd, False))
    # Check that hash of nonce is correct.
    err = validate_ciphertext(aes, in_file)
    if err:
        return err
    # Write decrypted data.
    _do_crypto(aes, in_file, out_file)


def main():
    op = None
    if len(sys.argv) >= 2:
        op = sys.argv[1]

    passwd = None
    if len(sys.argv) >= 3:
        passwd = sys.argv[2]

    if sys.hexversion < 0x03000000:
        in_file = sys.stdin
        out_file = sys.stdout
    else:
        in_file = sys.stdin.buffer
        out_file = sys.stdout.buffer

    err = None
    if op == "encrypt":
        encrypt(passwd, in_file, out_file)
    elif op == "decrypt":
        err = decrypt(passwd, in_file, out_file)
        if err:
            err = "Failed to decrypt: " + err
    else:
        err = "Usage: python aesutil.py {encrypt, decrypt} [passwd]"

    if err:
        print(err, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
