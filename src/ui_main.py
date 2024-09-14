from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QListWidget,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QPushButton,
    QLabel,
    QLineEdit,
    QAbstractItemView,
    QMessageBox,
    QCheckBox,
    QSpacerItem,
    QSizePolicy,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QItemSelection
from github_api import GitHubManager


class NonFollowerFetchThread(QThread):
    # Define custom signals to emit the results once the work is done
    finished = pyqtSignal(list, list, list)  # Non-followers, following, followers

    def __init__(self, github_manager, exclude_list):
        super().__init__()
        self.github_manager = github_manager
        self.exclude_list = exclude_list

    def run(self):
        # Fetch the data in this thread (instead of blocking the main thread)
        following = self.github_manager.get_following()
        followers = self.github_manager.get_followers()
        non_followers = self.github_manager.get_non_followers(self.exclude_list)

        # Sort the users based on login names (or any other criteria)
        following = sorted(following, key=lambda user: user.login.lower())
        followers = sorted(followers, key=lambda user: user.login.lower())
        non_followers = sorted(non_followers, key=lambda user: user.login.lower())

        # Emit the results back to the main thread
        self.finished.emit(non_followers, following, followers)


class UnFollowthread(QThread):
    # Signal to emit the count of users unfollowed once the process is complete
    unfollow_complete = pyqtSignal(int)

    def __init__(self, github_manager, exclude_list):
        super().__init__()
        self.github_manager = github_manager
        self.exclude_list = exclude_list

    def run(self):
        # Get non-followers from the manager
        non_followers = self.github_manager.get_non_followers(self.exclude_list)

        # Count the number of users unfollowed
        unfollowed_count = 0

        # Unfollow each non-follower
        for user in non_followers:
            self.github_manager.unfollow(user)
            unfollowed_count += 1

        # Emit the signal with the unfollowed count
        self.unfollow_complete.emit(unfollowed_count)


class NonFollowedFollowersFetchThread(QThread):
    finished = pyqtSignal(list)  # Signal to emit the list of non-followed followers

    def __init__(self, github_manager):
        super().__init__()
        self.github_manager = github_manager  # Store the GitHub manager for API calls

    def run(self):
        # Fetch followers and following lists
        followers = self.github_manager.get_followers()
        following = self.github_manager.get_following()

        # Find users who follow you but whom you are not following back
        non_followed_followers = [
            f for f in followers if f.login not in {u.login for u in following}
        ]

        # Emit the results when done
        self.finished.emit(non_followed_followers)


class FollowBackThread(QThread):
    # Signal to emit the count of users followed back when the process is complete
    finished = pyqtSignal(int)  # Signal to emit the number of users followed

    def __init__(self, github_manager, followers, following):
        super().__init__()
        self.github_manager = github_manager
        self.followers = followers
        self.following = following

    def run(self):
        # Convert to sets of usernames for easier comparison
        followers_set = set(user.login for user in self.followers)
        following_set = set(user.login for user in self.following)

        # Find the followers you're not following back
        to_follow_back = followers_set - following_set

        # Follow back each user
        followed_count = 0
        for user_login in to_follow_back:
            user = self.github_manager.g.get_user(user_login)
            self.github_manager.follow(user)
            followed_count += 1

        # Emit the number of users followed back
        self.finished.emit(followed_count)


class RepoFetchWorkerThread(QThread):
    finished = pyqtSignal(list)  # Signal to emit the list of starred repos

    def __init__(self, github_manager):
        super().__init__()
        self.github_manager = github_manager

    def run(self):
        # Fetch starred repos fro mthe GitHub API
        repos = self.github_manager.get_starred_repos()
        self.finished.emit(repos)


class UnstarReposWorkerThread(QThread):
    finished = pyqtSignal(int)  # Signal to emit the count of unstarred repos

    def __init__(self, github_manager, all_repos, repo_exclude_list):
        super().__init__()
        self.github_manager = github_manager
        self.all_repos = all_repos  # All repos in the listbox
        self.repo_exclude_list = repo_exclude_list  # Repos to exclude from unstarring

    def run(self):
        unstarred_count = 0

        for repo_name in self.all_repos:
            # Skip repositories that are in the exclude list
            if repo_name in self.repo_exclude_list:
                continue

            repo = self.github_manager.get_repo_by_name(repo_name)
            if repo:
                self.github_manager.unstar_repo(repo)
                unstarred_count += 1

        self.finished.emit(unstarred_count)


class MainWindow(QMainWindow):
    def __init__(self, github_manager):
        super().__init__()
        self.github_manager = github_manager
        self.exclude_list = []  # List of users to exclude
        self.repo_exclude_list = []
        self.non_followers = []  # Store non-followers to use in search functionality
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("FollowEqualizer")

        # Create main layout
        main_layout = QVBoxLayout()

        # Create horizontal layout for the list boxes
        lists_layout = QHBoxLayout()

        # Status label to show messages like "Ready"
        self.status_label = QLabel("Ready")
        main_layout.addWidget(self.status_label)

        # Add vertical space between status label and follower/following stats
        main_layout.addSpacerItem(
            QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Fixed)
        )

        # Label to show total numbers for following, followers, and non-followers
        self.total_following_label = QLabel("Following: 0")
        self.total_followers_label = QLabel("Followers: 0")
        self.non_follower_label = QLabel("Non-followers: 0")

        # Add the labels to the main layout
        main_layout.addWidget(self.total_following_label)
        main_layout.addWidget(self.total_followers_label)
        main_layout.addWidget(self.non_follower_label)

        # Add vertical space between status label and follower/following stats
        main_layout.addSpacerItem(
            QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Fixed)
        )

        self.clear_cache_checkbox = QCheckBox("Clear Cache")
        main_layout.addWidget(self.clear_cache_checkbox)

        main_layout.addSpacerItem(
            QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )

        ### NON-FOLLOWERS SECTION ###
        # Create a vertical layout for the Non-Followers list and its buttons
        non_followers_layout = QVBoxLayout()
        self.non_follower_list = QListWidget()
        self.non_follower_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.non_follower_list.setFixedHeight(
            250
        )  # Ensure all list boxes are the same height
        non_followers_layout.addWidget(QLabel("Non-Followers:"))
        non_followers_layout.addWidget(self.non_follower_list)

        # Vertical layout for buttons related to non-followers
        non_followers_button_layout = QVBoxLayout()
        self.find_non_followers_button = QPushButton("Find Non-Followers")
        self.find_non_followers_button.clicked.connect(
            self.start_fetch_non_followers_thread
        )

        self.unfollow_button = QPushButton("Unfollow Non-Followers")
        self.unfollow_button.clicked.connect(self.start_unfollow_thread)

        self.clear_non_followers_button = QPushButton("Clear Non-Followers")
        self.clear_non_followers_button.clicked.connect(self.clear_non_followers_list)

        non_followers_button_layout.addWidget(self.find_non_followers_button)
        non_followers_button_layout.addWidget(self.unfollow_button)
        non_followers_button_layout.addWidget(self.clear_non_followers_button)

        non_followers_layout.addLayout(non_followers_button_layout)

        ### USERS TO FOLLOW BACK SECTION ###
        # Create a vertical layout for the Users to Follow Back list and its buttons
        to_follow_layout = QVBoxLayout()
        self.to_follow_list = QListWidget()
        self.to_follow_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.to_follow_list.setFixedHeight(
            250
        )  # Ensure all list boxes are the same height
        to_follow_layout.addWidget(QLabel("Users to Follow Back:"))
        to_follow_layout.addWidget(self.to_follow_list)

        # Vertical layout for buttons related to users to follow back
        to_follow_button_layout = QVBoxLayout()

        # Find Non-Followed Followers and Connect to Thread
        self.find_non_followed_followers_button = QPushButton(
            "Find Non-Followed Followers"
        )
        self.find_non_followed_followers_button.clicked.connect(
            self.start_non_followed_followers_thread
        )

        # Follow back non-followed followers and connect to thread
        self.follow_back_button = QPushButton("Follow Back Non-Followed Followers")
        self.follow_back_button.clicked.connect(self.start_follow_back_thread)

        to_follow_button_layout.addWidget(self.find_non_followed_followers_button)
        to_follow_button_layout.addWidget(self.follow_back_button)

        # Add a spacer under the buttons to align the buttons horizontally
        to_follow_button_layout.addSpacerItem(
            QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )
        to_follow_layout.addLayout(to_follow_button_layout)

        ### REPOSITORIES TO UNSTAR SECTION ###
        # Create a vertical layout for the Repositories to Unstar list and its buttons
        repos_layout = QVBoxLayout()
        self.repo_list = QListWidget()
        self.repo_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.repo_list.setFixedHeight(250)  # Ensure all list boxes are the same height
        repos_layout.addWidget(QLabel("Repositories to Unstar:"))
        repos_layout.addWidget(self.repo_list)

        # Vertical layout for buttons related to repositories
        repos_button_layout = QVBoxLayout()

        self.find_repos_button = QPushButton("Find Repositories to Unstar")
        self.find_repos_button.clicked.connect(self.start_find_repos_to_unstar_thread)

        self.unstar_repos_button = QPushButton("Unstar Repositories")
        self.unstar_repos_button.clicked.connect(
            self.start_unstar_selected_repos_thread
        )

        repos_button_layout.addWidget(self.find_repos_button)
        repos_button_layout.addWidget(self.unstar_repos_button)

        # Add a spacer under the buttons to align the buttons horizontally
        repos_button_layout.addSpacerItem(
            QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )

        repos_layout.addLayout(repos_button_layout)

        # Add the three vertical layouts (Non-Followers, Users to Follow Back, Repositories to Unstar)
        lists_layout.addLayout(non_followers_layout)
        lists_layout.addLayout(to_follow_layout)
        lists_layout.addLayout(repos_layout)

        # Add the lists_layout to the main layout
        main_layout.addLayout(lists_layout)

        main_layout.addSpacerItem(
            QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )

        ### Adding the Clear All ListBox Selections button
        # button_layout = QHBoxLayout()  # Use a horizontal layout for the button

        self.selected_count_label = QLabel("Selected users: 0")
        main_layout.addWidget(self.selected_count_label)

        self.search_bar = QLineEdit(self)
        self.search_bar.setPlaceholderText(
            "Search non-followers or enter comma-separated usernames..."
        )
        self.search_bar.returnPressed.connect(self.handle_search)
        main_layout.addWidget(self.search_bar)

        self.clear_all_listbox_selections_button = QPushButton(
            "Clear All ListBox Selections"
        )
        self.clear_all_listbox_selections_button.clicked.connect(
            self.clear_all_listbox_selections
        )
        self.clear_all_listbox_selections_button.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )

        main_layout.addWidget(self.clear_all_listbox_selections_button)

        self.add_selected_listbox_items_to_exceptions_button = QPushButton(
            "Add Selected to Exceptions"
        )
        self.add_selected_listbox_items_to_exceptions_button.clicked.connect(
            self.add_selected_listbox_items_to_exceptions
        )

        main_layout.addWidget(self.add_selected_listbox_items_to_exceptions_button)

        # Add the button to the layout without stretches (to make it span the full width)
        # main_layout.addLayout(button_layout)

        main_layout.addSpacerItem(
            QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )

        self.exclude_list_label = QLabel("Exceptions:")
        self.exclude_list_box = QListWidget()
        main_layout.addWidget(self.exclude_list_label)
        main_layout.addWidget(self.exclude_list_box)

        self.remove_exception_button = QPushButton("Remove Selected Exception")
        self.remove_exception_button.clicked.connect(self.remove_selected_exception)

        self.clear_exceptions_button = QPushButton("Clear All Exceptions")
        self.clear_exceptions_button.clicked.connect(self.clear_all_exceptions)

        main_layout.addWidget(self.remove_exception_button)
        main_layout.addWidget(self.clear_exceptions_button)

        # Set the layout for the main widget
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def handle_search(self):
        # Get the search input from the search bar
        search_term = self.search_bar.text()

        # Check if the input contains commas (indicating multiple search terms)
        if "," in search_term:
            # Split the input by commas to get a list of search terms
            search_terms = [term.strip() for term in search_term.split(",")]
            # Pass the search terms list to the select_items_from_list function
            self.select_items_from_list(search_terms)
        else:
            # Handle a single search term by searching across all lists
            self.search_across_lists(search_term)

        # Clear the search bar after the search is executed
        self.search_bar.clear()

    def select_items_from_list(self, search_terms):
        # Track whether any matches are found
        found_match = False

        # Loop through each search term and search in all list boxes
        for search_term in search_terms:
            # Search across all list widgets for matching items
            found_match = (
                self.search_list(self.non_follower_list, search_term) or found_match
            )
            found_match = self.search_list(self.repo_list, search_term) or found_match
            found_match = (
                self.search_list(self.to_follow_list, search_term) or found_match
            )

        # Update the status label to indicate whether any matches were found
        if found_match:
            self.status_label.setText("Matching items found.")
        else:
            self.status_label.setText("No matching items found.")

        # Update the count of selected items
        self.update_selected_count()

    def search_across_lists(self, search_term):
        search_term = search_term.lower()  # Case-insensitive search

        # Track whether any matches are found
        found_match = False

        # Search in the non-followers list
        found_match = (
            self.search_list(self.non_follower_list, search_term) or found_match
        )

        # Search in the repositories list
        found_match = self.search_list(self.repo_list, search_term) or found_match

        # Search in the users to follow list
        found_match = self.search_list(self.to_follow_list, search_term) or found_match

        # Update the status label based on whether a match was found
        if found_match:
            self.status_label.setText("Matching items found.")
        else:
            self.status_label.setText("No matching items found.")

        # Update the count of selected items
        self.update_selected_count()

    def search_list(self, list_widget, search_term):
        """Helper function to search for a term in a given list widget."""
        found_match = False
        last_matched_item = None

        # Iterate through all items in the list
        for index in range(list_widget.count()):
            item = list_widget.item(index)
            item_text = item.text().lower()

            # If the search term matches, select the item
            if search_term.lower() in item_text:
                item.setSelected(True)  # Select matching item
                last_matched_item = item  # Track the last matched item for scrolling
                found_match = True

        # Scroll to the last matched item if any were found
        if found_match and last_matched_item:
            list_widget.scrollToItem(last_matched_item)

        return found_match

    def start_fetch_non_followers_thread(self):
        # Clear the UI lists before starting the thread
        self.clear_non_followers_list()

        # Check if the cache should be cleared
        if self.clear_cache_checkbox.isChecked():
            self.github_manager.clear_internal_cache()

        # Update the status label to indicate the app is working
        self.status_label.setText("Gathering Non-Followers...")

        # Disable the button while fetching
        self.find_non_followers_button.setEnabled(False)

        self.non_follow_fetch_worker = NonFollowerFetchThread(
            self.github_manager, self.exclude_list
        )
        self.non_follow_fetch_worker.finished.connect(self.on_non_followers_fetched)
        self.non_follow_fetch_worker.start()

    def on_non_followers_fetched(self, non_followers, following, followers):
        # Update the UI elements with the fetched data
        # For example:

        self.non_follower_list.addItems([user.login for user in non_followers])
        self.total_following_label.setText(f"Following: {len(following)}")
        self.total_followers_label.setText(f"Followers: {len(followers)}")
        self.non_follower_label.setText(f"Non-followers: {len(non_followers)}")

        # Re-enable the button
        self.find_non_followers_button.setEnabled(True)

        # Update the status label
        self.status_label.setText("Non-Followers Updated")

    def start_unfollow_thread(self):
        # Update the status label to indicate the process has started
        self.status_label.setText("Unfollowing non-followers...")

        # Disable the button while the process is running
        self.unfollow_button.setEnabled(False)

        # Create and start the worker thread
        self.unfollow_non_followers_worker = UnFollowthread(
            self.github_manager, self.exclude_list
        )
        self.unfollow_non_followers_worker.unfollow_complete.connect(
            self.on_unfollow_complete
        )
        self.unfollow_non_followers_worker.start()

    def on_unfollow_complete(self, unfollowed_count):
        # Re-enable the button after unfollowing is complete
        self.unfollow_button.setEnabled(True)

        # Update the status label to "Ready"
        self.status_label.setText("Ready")

        # Show a message box with the unfollow success message
        QMessageBox.information(
            self,
            "Unfollow Success",
            f"Successfully unfollowed {unfollowed_count} users who are not following you.",
        )

    def clear_non_followers_list(self):
        self.non_follower_list.clear()

        self.non_follower_label.setText("Non-followers: 0")
        self.total_following_label.setText("Following: 0")
        self.total_followers_label.setText("Followers: 0")

        self.status_label.setText("Ready")

    def start_non_followed_followers_thread(self):
        self.status_label.setText("Retrieving Non-Followed Followers...")
        self.worker_thread = NonFollowedFollowersFetchThread(self.github_manager)
        self.worker_thread.finished.connect(self.on_non_followed_users_fetched)
        self.worker_thread.start()

    def on_non_followed_users_fetched(self, users):
        self.to_follow_list.clear()  # Clear the list before adding new users
        for user in users:
            self.to_follow_list.addItem(
                user.login
            )  # Add the user to the list in the UI
        self.status_label.setText("Ready")

    def start_follow_back_thread(self):

        self.status_label.setText("Following Users You've Yet To Follow...")
        # Disable the button while following users
        self.follow_back_button.setEnabled(False)

        # Get followers and following lists
        followers = self.github_manager.get_followers()
        following = self.github_manager.get_following()

        # Create and start the worker thread
        self.follow_back_thread = FollowBackThread(
            self.github_manager, followers, following
        )
        self.follow_back_thread.finished.connect(self.on_follow_back_complete)
        self.follow_back_thread.start()

    def on_follow_back_complete(self, followed_count):
        # Re-enable the button after the operation is complete
        self.follow_back_button.setEnabled(True)

        # Update the UI with the number of users followed
        self.status_label.setText(f"Followed back {followed_count} users.")

        # Refresh the "to follow" list (optional)
        # self.update_follow_back_list()

    def update_follow_back_list(self):
        # Get followers and following lists again to update the "to follow" list
        followers = self.github_manager.get_followers()
        following = self.github_manager.get_following()

        # Convert to sets of usernames for easier comparison
        followers_set = set(user.login for user in followers)
        following_set = set(user.login for user in following)

        # Find the followers you're not following back
        to_follow_back = followers_set - following_set

        # Clear the "to follow" list box and repopulate it
        self.to_follow_list.clear()
        for user_login in to_follow_back:
            self.to_follow_list.addItem(user_login)

    def start_find_repos_to_unstar_thread(self):

        # Update the status label to indicate the app is working
        self.status_label.setText("Searching for Repos to Unstar...")
        self.repo_worker_thread = RepoFetchWorkerThread(self.github_manager)
        self.repo_worker_thread.finished.connect(self.on_repos_fetched)
        self.repo_worker_thread.start()

    def on_repos_fetched(self, repos):
        self.repo_list.clear()
        for repo in repos:
            self.repo_list.addItem(
                repo.full_name
            )  # Add each repo's full name to the list([iterable])
        self.status_label.setText("Ready")

    def start_unstar_selected_repos_thread(self):
        self.status_label.setText("Unstarring Repositories...")
        # Get all repositories from the "Repos to Unstar" listbox
        all_repos = [
            self.repo_list.item(i).text() for i in range(self.repo_list.count())
        ]

        # Get the selected repositories to add to the exception list
        selected_repos = [
            repo_item.text() for repo_item in self.repo_list.selectedItems()
        ]

        # Add selected repos to the exception list
        for repo_name in selected_repos:
            if repo_name not in self.repo_exclude_list:
                self.repo_exclude_list.append(repo_name)
                self.exclude_list_box.addItem(repo_name)  # Add to exceptions display

        # Start the unstar process for all repositories except the selected ones
        self.unstar_repo_worker_thread = UnstarReposWorkerThread(
            self.github_manager, all_repos, self.repo_exclude_list
        )
        self.unstar_repo_worker_thread.finished.connect(self.on_repos_unstarred)
        self.unstar_repo_worker_thread.start()

    def on_repos_unstarred(self, unstarred_count):
        self.status_label.setText(f"Unstarred {unstarred_count} repositories.")

        # Refresh the repo list after unstarring
        self.start_find_repos_to_unstar_thread()
        self.clear_all_exceptions()

    def clear_all_listbox_selections(self):
        self.non_follower_list.clearSelection()  # Clear selection from non-followers list
        self.repo_list.clearSelection()  # Clear selection from repositories list
        self.to_follow_list.clearSelection()  # Clear selection from follow-back list

        self.update_selected_count()  # Update count after clearing selection

    def add_selected_listbox_items_to_exceptions(self):
        # Handle non-followers (users) selection
        selected_users = self.non_follower_list.selectedItems()
        for item in selected_users:
            username = item.text()
            if (
                username not in self.exclude_list
            ):  # Assuming self.exclude_list is for users
                self.exclude_list.append(username)
                self.exclude_list_box.addItem(username)  # Add user to exceptions list

        # Handle repositories selection
        selected_repos = self.repo_list.selectedItems()
        for item in selected_repos:
            repo_name = item.text()
            if (
                repo_name not in self.repo_exclude_list
            ):  # Assuming self.repo_exclude_list is for repos
                self.repo_exclude_list.append(repo_name)
                self.exclude_list_box.addItem(repo_name)  # Add repo to exceptions list

        # Handle users to follow back selection
        selected_to_follow = self.to_follow_list.selectedItems()
        for item in selected_to_follow:
            username = item.text()
            if (
                username not in self.exclude_list
            ):  # Assuming self.exclude_list is for users
                self.exclude_list.append(username)
                self.exclude_list_box.addItem(username)  # Add user to exceptions list

        # Update the selected count after adding
        self.update_selected_count()

        # Clear the selection from all list boxes

    def remove_selected_exception(self):
        selected_items = self.exclude_list_box.selectedItems()
        if selected_items:
            for item in selected_items:
                self.exclude_list.remove(item.text())  # Remove from the exclude list
                self.exclude_list_box.takeItem(
                    self.exclude_list_box.row(item)
                )  # Remove from the list box

    def clear_all_exceptions(self):
        self.exclude_list.clear()
        self.repo_exclude_list.clear()
        self.non_followers.clear()
        self.exclude_list_box.clear()

    def update_selected_count(self):
        # Count selected items from each list
        non_follower_selected = len(self.non_follower_list.selectedItems())
        to_follow_selected = len(self.to_follow_list.selectedItems())
        repo_selected = len(self.repo_list.selectedItems())

        # Calculate total selected items
        total_selected = non_follower_selected + to_follow_selected + repo_selected

        # Update the label with the total count
        self.selected_count_label.setText(f"Selected items: {total_selected}")
