from beem import Steem
from beem.account import Account
from beem.comment import Comment, RecentReplies
from datetime import date, datetime, timedelta
from dateutil.parser import parse
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import json
import logging
import os
import time

# Minimum score required to be resteemed
MINIMUM_SCORE = 10

# Get path of current folder
DIR_PATH = os.path.dirname(os.path.realpath(__file__))

# Logging
logger = logging.getLogger("utopian-io")
logger.setLevel(logging.INFO)
fh = logging.FileHandler(f"{DIR_PATH}/bot.log")
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
fh.setFormatter(formatter)
logger.addHandler(fh)

# Beem
steem = Steem()
ACCOUNT = "utopian.tasks"

# Spreadsheet variables
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name(
    f"{DIR_PATH}/client_secret.json", scope)
client = gspread.authorize(credentials)
sheet = client.open("Utopian Reviews")

# Get date of current, next and previous Thursday
today = date.today()
offset = (today.weekday() - 3) % 7
this_week = today - timedelta(days=offset)
last_week = this_week - timedelta(days=7)
next_week = this_week + timedelta(days=7)

# Get title's of most recent two worksheets
title_previous = f"Reviewed - {last_week:%b %-d} - {this_week:%b %-d}"
title_current = f"Reviewed - {this_week:%b %-d} - {next_week:%b %-d}"
previous_reviewed = sheet.worksheet(title_previous)
current_reviewed = sheet.worksheet(title_current)


def main():
    """
    Checks if post's score has been changed to zero and unvotes it if
    necessary.
    """
    # Get data from both the current sheet and previous one
    previous = previous_reviewed.get_all_values()
    current = current_reviewed.get_all_values()
    reviewed = previous[1:] + current[1:]

    account = Account(ACCOUNT)
    # Resteem all eligible contributions that haven't been resteemed already
    for row in reviewed:
        category = row[4]
        score = float(row[5])
        if "task" in category and score > MINIMUM_SCORE:
            url = row[2]
            post = Comment(url)
            if ACCOUNT not in post.get_reblogged_by():
                post.resteem(account=account)

if __name__ == '__main__':
    main()
