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
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QPushButton, QLineEdit, QFileDialog, QMessageBox
from PyQt5.QtGui import QPixmap, QIcon
import sys
import warnings

from styx import (
    AlreadyEncryptedError,
    LegacyFormatWarning,
    StyxError,
    decrypt_file,
    decrypt_folder,
    encrypt_file,
    encrypt_folder,
)


def _summarize(done, failed, skipped, legacy, verb):
    """Build the message shown after an encrypt/decrypt run."""
    lines = [f"{done} file(s) {verb}."]
    if skipped:
        lines.append(f"{len(skipped)} skipped:")
        lines += [f"  {p}: {why}" for p, why in skipped[:10]]
    if failed:
        lines.append(f"{len(failed)} failed (file left unchanged):")
        lines += [f"  {p}: {why}" for p, why in failed[:10]]
    if legacy:
        lines.append(f"{len(legacy)} file(s) were in the old unauthenticated format. "
                     "Encrypt them again to upgrade them.")
    return "\n".join(lines)

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

class MainWindow(QMainWindow):


    file_paths = []
    folder_paths = []

    def __init__(self):
        super().__init__()

        # Set window title
        self.setWindowTitle("STYX")

        # Set window icon
        self.setWindowIcon(QIcon(resource_path('Styx_icon.png')))

        # Set window size
        self.setGeometry(100, 100, 600, 290)

        # Set background image
        background = QLabel(self)
        pixmap = QPixmap(resource_path('background.jpg'))
        background.setPixmap(pixmap)
        background.resize(self.width(), self.height())

        # Set title label
        title = QLabel("STYX", self)
        title.move(250, 50)
        title.setStyleSheet("font-size: 40px; font-weight: bold; color: white")

        # Set encrypt button
        encrypt_button = QPushButton("Encrypt", self)
        encrypt_button.move(200, 115)
        encrypt_button.resize(200, 50)
        encrypt_button.setStyleSheet("background-color: white; color: black; font-weight: bold; font-size: 20px; border: 2px solid dark;")
        encrypt_button.clicked.connect(lambda: self.handleButtonClick("Encrypt"))

        # Set decrypt button
        decrypt_button = QPushButton("Decrypt", self)
        decrypt_button.move(200, 185)
        decrypt_button.resize(200, 50)
        decrypt_button.setStyleSheet("background-color: white; color: black; font-weight: bold; font-size: 20px; border: 2px solid dark;")
        decrypt_button.clicked.connect(lambda: self.handleButtonClick("Decrypt"))

    # Handler for button click
    def handleButtonClick(self, action):

        # Close current window
        self.close()

        # Open new window
        self.newWindow = QWidget()
        self.newWindow.setWindowTitle(action)
        self.newWindow.setGeometry(100, 100, 600, 400)
        self.newWindow.setWindowIcon(QIcon(resource_path('Styx_icon.png')))

        # Set background image
        background = QLabel(self.newWindow)
        pixmap = QPixmap(resource_path('background.jpg'))
        background.setPixmap(pixmap)
        background.resize(self.newWindow.width(), self.newWindow.height())

        # Set file explorer button
        file_button = QPushButton("Choose File(s)", self.newWindow)
        file_button.setGeometry(170, 30, 130, 40)
        file_button.setStyleSheet("background-color: lightGray; color: black; font-weight: bold; border: 2px solid dark;")
        file_button.clicked.connect(self.showDialogFile)

        # Set folder explorer button
        folder_button = QPushButton("Choose Folder", self.newWindow)
        folder_button.setGeometry(298, 30, 130, 40)
        folder_button.setStyleSheet("background-color: lightGray; color: black; font-weight: bold; border: 2px solid dark;")
        folder_button.clicked.connect(self.showDialogFolder)

        # Set password input field
        password_label = QLabel("Password :", self.newWindow)
        password_label.setStyleSheet("color: white; font-weight: italic; font-size: 17px;")
        password_label.move(50, 100)

        password_input = QLineEdit(self.newWindow)
        password_input.setEchoMode(QLineEdit.Password)
        password_input.move(200, 100)
        password_input.resize(200, 25)

        # Set confirm password input field if encrypting
        if action == "Encrypt":

            self.newWindow.setGeometry(100, 100, 600, 335)

            confirm_label = QLabel("Confirm Password :", self.newWindow)
            confirm_label.setStyleSheet("color: white; font-weight: italic; font-size: 17px;")
            confirm_label.move(50, 150)

            confirm_input = QLineEdit(self.newWindow)
            confirm_input.setEchoMode(QLineEdit.Password)
            confirm_input.move(200, 150)
            confirm_input.resize(200, 25)

            confirm_show_password_button = QPushButton("Show Password", self.newWindow)
            confirm_show_password_button.move(420, 145)
            confirm_show_password_button.setStyleSheet("background-color: gray; color: black; font-weight: bold;")
            confirm_show_password_button.clicked.connect(lambda: self.handleShowPassword(confirm_input))

            def handle_encrypt_clicked(self, file_paths,folder_paths):
                password = password_input.text()
                confirm_password = confirm_input.text()
                if password != confirm_password:
                    error_dialog = QMessageBox()
                    error_dialog.setIcon(QMessageBox.Critical)
                    error_dialog.setWindowTitle("Error")
                    error_dialog.setText("WRONG PASSWORDS")
                    error_dialog.setStandardButtons(QMessageBox.Ok)
                    error_dialog.exec_()
                elif not password:
                    QMessageBox.critical(self.newWindow, "Error", "The password must not be empty.")
                else:
                    done, failed, skipped = 0, [], []
                    for file in file_paths:
                        for f in file:
                            try:
                                encrypt_file(f, password)
                                done += 1
                            except AlreadyEncryptedError:
                                skipped.append((f, "already encrypted"))
                            except (OSError, StyxError) as exc:
                                failed.append((f, str(exc)))
                    for folder in folder_paths:
                        report = encrypt_folder(folder, password)
                        done += len(report.processed)
                        failed += report.failed
                        skipped += report.skipped

                    message = _summarize(done, failed, skipped, [], "encrypted")
                    if failed:
                        QMessageBox.critical(self.newWindow, "Error while encrypting", message)
                    else:
                        QMessageBox.information(self, "Success", message)
                        self.newWindow.close()
                        self.show()

        # Set back button
            back_button = QPushButton("Back", self.newWindow)
            back_button.setGeometry(200, 260, 200, 50)
            back_button.setStyleSheet("background-color: white; color: black; font-weight: bold; font-size: 20px; border: 2px solid dark;")
            back_button.clicked.connect(self.handleBackButtonClick)

            # Set encrypt/decrypt button
            submit_button_E = QPushButton(action.capitalize(), self.newWindow)
            submit_button_E.move(200, 200)
            submit_button_E.resize(200, 50)
            submit_button_E.setStyleSheet("background-color: white; color: black; font-weight: bold; font-size: 20px; border: 2px solid dark;")
            submit_button_E.clicked.connect(lambda : handle_encrypt_clicked(self,self.file_paths,self.folder_paths))

        elif action == "Decrypt":

            self.newWindow.setGeometry(100, 100, 600, 280)

            # Set back button
            back_button = QPushButton("Back", self.newWindow)
            back_button.setGeometry(200, 210, 200, 50)
            back_button.setStyleSheet("background-color: white; color: black; font-weight: bold; font-size: 20px; border: 2px solid dark;")
            back_button.clicked.connect(self.handleBackButtonClick)

            def handle_decrypt_clicked(self, file_paths, folder_paths):
                password = password_input.text()
                if not password:
                    QMessageBox.critical(self.newWindow, "Error", "The password must not be empty.")
                    return
                done, failed, skipped, legacy = 0, [], [], []
                for file in file_paths:
                    for f in file:
                        try:
                            with warnings.catch_warnings():
                                warnings.simplefilter("ignore", LegacyFormatWarning)
                                if decrypt_file(f, password) == 0:
                                    legacy.append(f)
                            done += 1
                        except (OSError, StyxError) as exc:
                            failed.append((f, str(exc)))
                for folder in folder_paths:
                    report = decrypt_folder(folder, password)
                    done += len(report.processed)
                    failed += report.failed
                    skipped += report.skipped
                    legacy += report.legacy

                message = _summarize(done, failed, skipped, legacy, "decrypted")
                if failed:
                    QMessageBox.critical(self.newWindow, "Error while decrypting",
                                         message + "\nCheck your password.")
                elif legacy:
                    QMessageBox.warning(self, "Decrypted (legacy format)", message)
                    self.newWindow.close()
                    self.show()
                else:
                    QMessageBox.information(self, "Success", message)
                    self.newWindow.close()
                    self.show()

# Set encrypt/decrypt button
            submit_button_D = QPushButton(action.capitalize(), self.newWindow)
            submit_button_D.move(200, 150)
            submit_button_D.resize(200, 50)
            submit_button_D.setStyleSheet("background-color: white; color: black; font-weight: bold; font-size: 20px; border: 2px solid dark;")
            submit_button_D.clicked.connect(lambda : handle_decrypt_clicked(self,self.file_paths,self.folder_paths))

        # Set show password button
        show_password_button = QPushButton("Show Password", self.newWindow)
        show_password_button.move(420, 95)
        show_password_button.setStyleSheet("background-color: gray; color: black; font-weight: bold;")
        show_password_button.clicked.connect(lambda: self.handleShowPassword(password_input))

        # Show new window
        self.newWindow.show()

    # Handler for file explorer button click
    def showDialogFile(self):

        self.file_paths.clear()

        file_dialog = QFileDialog()
        # Set file filter to only show files
        file_dialog.setFileMode(QFileDialog.ExistingFiles)

        # Show the file explorer dialog and get selected file path
        if file_dialog.exec_():
            selected_files = file_dialog.selectedFiles()
            self.file_paths.append(selected_files)

    # Handler for folder explorer button click
    def showDialogFolder(self):

        self.folder_paths.clear()

        options = QFileDialog.Options()
        folder_path = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier", options=options)

        if folder_path:
            self.folder_paths.append(folder_path)


    # Handler for show password button click
    def handleShowPassword(self, password_input):
        if password_input.echoMode() == QLineEdit.Password:
            password_input.setEchoMode(QLineEdit.Normal)
        else:
            password_input.setEchoMode(QLineEdit.Password)

    # Handler for back button click
    def handleBackButtonClick(self):
        # Close current window
        self.newWindow.close()

        # Open main window
        self.show()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec_())