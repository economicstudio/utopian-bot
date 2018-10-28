"""
Class for handling the sqlite3 database which stores contributions upvoted
while following the trail.
"""

import os
import sqlite3


class DatabaseHandler():
    class __DatabaseHandler():
        dir_path = os.path.dirname(os.path.abspath(__file__))

        def __init__(self):
            database_path = os.path.join(self.dir_path, "utopian-io.db")

            if not os.path.exists(database_path):
                try:
                    self.create_database(database_path)
                except Exception:
                    pass

            self.connection = sqlite3.connect(database_path)
            self.connection.text_factory = lambda x: str(x, "utf-8", "ignore")
            self.cursor = self.connection.cursor()

        @staticmethod
        def create_database(database_path: str) -> None:
            """Create database file and contributions table to the database."""
            open(database_path, "a").close()

            connection = sqlite3.connect(database_path)
            connection.text_factory = lambda x: str(x, "utf-8", "ignore")
            cursor = connection.cursor()

            cursor.execute("CREATE TABLE 'contributions'"
                           "('contributionID' INTEGER NOT NULL,"
                           "'trail' TEXT,"
                           "'authorperm' TEXT,"
                           "'upvote_date' TEXT,"
                           "PRIMARY KEY('contributionID'));")

            connection.commit()
            connection.close()

        def number_upvoted(self, trail: str, upvote_date: str) -> int:
            """Returns the number of contributions upvoted following the given
            trail after a given date.

            :param str trail: The trail the contribution is a part of.
            :param str upvote_date: The time the contribution was upvoted by
                utopian-io.
            """
            self.cursor.execute("SELECT count(*) FROM contributions WHERE "
                                "trail=? AND upvote_date > ?;",
                                [str(trail), str(upvote_date)])

            result = self.cursor.fetchone()
            return result[0]

        def add_contribution(self, contribution_id: int, trail: str,
                             authorperm: str, upvote_date: str) -> None:
            """Add contribution to the `contributions` table.

            :param int contribution_id: A contribution's ID.
            :param str trail: The trail the contribution is a part of.
            :param str authorperm: The contribution's authorperm.
            :param str upvote_date: The time the contribution was upvoted by
                utopian-io.
            """
            try:
                self.cursor.execute(
                    "INSERT INTO contributions VALUES (?, ?, ?, ?);",
                    (str(contribution_id), trail, authorperm, upvote_date))
                self.connection.commit()
            except sqlite3.IntegrityError:
                pass

        def contribution_exists(self, authorperm: str) -> bool:
            """Returns True if a contribution with the given `authorperm`
            exists in the database, otherwise False.

            :param str authorperm: The contribution's authorperm.
            """
            self.cursor.execute("SELECT rowid, * FROM contributions WHERE "
                                "authorperm=?;", [str(authorperm)])

            result = self.cursor.fetchall()
            if len(result) > 0:
                return True
            else:
                return False

        def close_connection(self) -> None:
            self.connection.close()

    instance = None

    def __init__(self):
        if not DatabaseHandler.instance:
            DatabaseHandler.instance = DatabaseHandler.__DatabaseHandler()

    @staticmethod
    def get_instance() -> __DatabaseHandler:
        if not DatabaseHandler.instance:
            DatabaseHandler.instance = DatabaseHandler.__DatabaseHandler()

        return DatabaseHandler.instance
