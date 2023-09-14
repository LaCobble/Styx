# Projet : Styx
# Author:
#      __          ___      _     _     _
#     / /  __ _   / __\___ | |__ | |__ | | ___
#    / /  / _` | / /  / _ \| '_ \| '_ \| |/ _ \
#   / /__| (_| |/ /__| (_) | |_) | |_) | |  __/
#   \____/\__,_|\____/\___/|_.__/|_.__/|_|\___|
#
#

import os
import string
import secrets
import sys
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding

# Encrypt a file with a password
def encrypt(path, password):

    # Generate a random 16-byte initialization vector
    iv = os.urandom(16)

    # Generate a random salt
    salt = os.urandom(16)

    # Derive an encryption key from the password and salt
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    key = kdf.derive(password.encode('utf-8'))

    # Encrypt the file contents
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    padder = padding.PKCS7(128).padder()
    with open(path, 'rb') as f:
        data = f.read()
    padded_data = padder.update(data) + padder.finalize()
    ct = encryptor.update(padded_data) + encryptor.finalize()

    # Write the encrypted file contents
    with open(path, 'wb') as f:
        f.write(salt)
        f.write(iv)
        f.write(ct)

# Decrypt a file with a password
def decrypt(path, password):

    try:
        # Read the encrypted file contents
        with open(path, 'rb') as f:
            salt = f.read(16)
            iv = f.read(16)
            ct = f.read()

        # Derive the encryption key from the password and salt
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = kdf.derive(password.encode('utf-8'))

        # Decrypt the file contents
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(ct) + decryptor.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        data = unpadder.update(padded_data) + unpadder.finalize()

        # Write the decrypted file contents
        with open(path, 'wb') as f:
            f.write(data)
    except:
        pass

# Encrypt a folder with a password
def encrypt_folder(folder, password):
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        if os.path.isfile(file_path):
            encrypt(file_path, password)
        elif os.path.isdir(file_path):
            encrypt_folder(file_path, password)

# Decrypt a folder with a password
def decrypt_folder(folder, password):
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        if os.path.isfile(file_path):
            decrypt(file_path, password)
        elif os.path.isdir(file_path):
            decrypt_folder(file_path, password)