![Styx](Styx.png)

Styx is a Python script for file encryption and decryption. The script uses AES encryption and PBKDF2 key derivation algorithm to encrypt and decrypt files and folders. The script also has a function to send an email with the decryption key, which includes the IP address, encryption key, and time of encryption. The user should configure the SMTP server with the correct details for the email function to work.


## Dependencies

```txt
The dependencies for the script are:

os: to access the underlying operating system to access files and directories
smtplib: to send an email
string: to use string manipulation functions
getpass: to get the password securely without printing it on the console
platform: to determine the system properties
datetime: to get the current time
secrets: to generate random numbers
sys: to access system functions
socket: to get the IP address of the computer
art: to generate ASCII art
cryptography: to perform cryptography functions like encryption, decryption, and key derivation
email.mime.text: to create the text of the email to be sent
```

## Usage

```python
python Styx.py
```

## License

[MIT](https://choosealicense.com/licenses/mit/)