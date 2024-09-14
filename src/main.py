from PyQt5.QtWidgets import QApplication
from github_api import GitHubManager
from ui_main import MainWindow
from dotenv import load_dotenv, find_dotenv
from pathlib import Path
import os

if __name__ == "__main__":

    # Absolute path to the .env file
    dotenv_path = Path(__file__).resolve().parent.parent / ".env"

    load_dotenv(dotenv_path)

    github_token = os.getenv("GITHUB_TOKEN")

    # Create the Qt application
    app = QApplication([])

    # Create your GitHub manager instance with the token
    github_manager = GitHubManager(github_token)

    # Create the main window
    window = MainWindow(github_manager)
    window.show()

    # Execute the application
    app.exec_()
