import logging
import gspread
import json
import os
import time
from beem import Steem
from beem.account import Account
from beem.comment import Comment, RecentReplies
from datetime import date, datetime, timedelta
from dateutil.parser import parse
from oauth2client.service_account import ServiceAccountCredentials

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
ACCOUNT = "utopian-io"

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


def get_replies(post):
    """
    Gets all replies to the given post.
    """
    url = f"{post.category}/{post.authorperm}"
    return steem.rpc.get_state(url)["content"].keys()


def update_comment(post):
    """
    Updates the comment left by the bot to reflect that the contribution was
    unvoted.
    """
    body = (f"Hey @{post.author}, your contribution was unvoted because we "
            "found out that it did not follow the "
            "[Utopian rules](https://utopian.io/rules).\n\n Upvote this "
            "comment to help Utopian grow its power and help other Open "
            "Source contributions like this one.\n\n**Want to chat? Join us "
            "on [Discord](https://discord.gg/Pc8HG9x).**")

    # Iterate over replies until bot's comment is found
    for comment in get_replies(post):
        comment = Comment(comment)
        if comment.author == ACCOUNT and comment.is_comment():
            try:
                logger.info(f"Updating comment {comment.authorperm}")
                comment.edit(body, replace=True)
            except Exception as error:
                logger.error(error)
            return
            


def unvote_post(row, previous, current):
    """
    Unvotes the given post and updates the spreadsheet to reflect this.
    """
    url = row[2]
    account = Account(ACCOUNT)
    post = Comment(url, steem_instance=steem)

    # Check if actually voted on post
    votes = [vote["voter"] for vote in post.json()["active_votes"]]
    if ACCOUNT not in votes:
        logger.info(f"Never voted on {url} in the first place!")
        return

    # Unvote the post
    try:
        logger.info(f"Unvoting {url}")
        post.vote(0, account=account)
        time.sleep(3)
        # Edit comment
        update_comment(post)
    except Exception as error:
        logger.error(error)

    # Just in case sheet was updated in the meantime
    previous_reviewed = sheet.worksheet(title_previous)
    current_reviewed = sheet.worksheet(title_current)

    # Update row depending on which sheet it's in
    if row in previous:
        row_index = previous.index(row) + 1
        previous_reviewed.update_cell(row_index, 10, "Unvoted")
        previous_reviewed.update_cell(row_index, 11, 0)
    elif row in current:
        row_index = current.index(row) + 1
        current_reviewed.update_cell(row_index, 10, "Unvoted")
        current_reviewed.update_cell(row_index, 11, 0)


def main():
    """
    Checks if post's score has been changed to zero and unvotes it if
    necessary.
    """
    # Get data from both the current sheet and previous one
    previous = previous_reviewed.get_all_values()
    current = current_reviewed.get_all_values()
    reviewed = previous[1:] + current[1:]

    # If file already exists compare with current data
    if os.path.isfile(f"{DIR_PATH}/reviews.json"):
        with open(f"{DIR_PATH}/reviews.json") as fd:
            data = json.load(fd)
        for row in reviewed:
            # Row has been changed
            if row not in data:
                voted_on = row[-2]
                score = float(row[5])
                # Only unvote posts with score 0 that have been voted on
                if score == 0 and voted_on == "Yes":
                    unvote_post(row, previous, current)

    # Save current data
    with open(f"{DIR_PATH}/reviews.json", "w") as fd:
        json.dump(reviewed, fd, indent=4)

if __name__ == '__main__':
    main()
