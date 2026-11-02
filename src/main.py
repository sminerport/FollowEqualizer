import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from PyQt5.QtWidgets import QApplication, QMessageBox

from github_api import GitHubManager
from ui_main import MainWindow

if __name__ == "__main__":
    # Absolute path to the .env file
    dotenv_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path)
    github_token = os.getenv("GITHUB_TOKEN")

    # Create the Qt application
    app = QApplication([])

    if not github_token:
        QMessageBox.critical(
            None,
            "FollowEqualizer",
            f"GITHUB_TOKEN is not set.\nAdd it to {dotenv_path} or your environment.",
        )
        sys.exit(1)

    # Create your GitHub manager instance with the token
    github_manager = GitHubManager(github_token)

    # Create the main window
    window = MainWindow(github_manager)
    window.show()

    # Execute the application
    sys.exit(app.exec_())
