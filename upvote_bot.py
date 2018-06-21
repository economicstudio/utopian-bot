from beem import Steem
from beem.account import Account
from beem.comment import Comment
from datetime import date, datetime, timedelta
from dateutil.parser import parse
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import logging
import os

# Get path of current folder
DIR_PATH = os.path.dirname(os.path.realpath(__file__))

# The minimum age a post must be to receive an upvote
MINIMUM_AGE = 24

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

MAX_VOTE = {
    "ideas": 12.0,
    "development": 40.0,
    "bug-hunting": 8.0,
    "translations": 25.0,
    "graphics": 30.0,
    "analysis": 35.0,
    "social": 20.0,
    "documentation": 20.0,
    "tutorials": 20.0,
    "video-tutorials": 25.0,
    "copywriting": 20.0,
    "blog": 20.0,
}

CORRECT_BENEFICIARIES = [
    {
        "account": "davinci.pay",
        "weight": 1000
    },
    {
        "account": "utopian.pay",
        "weight": 500
    }
]


def bot_comment(post, category, account, staff_picked=False):
    """
    Comments on the given post. Content changes depending on the category and
    if the post was staff picked or not.
    """
    # Change text depending on if contribution is task request or not
    if "task" in category:
        contribution = "task request"
    else:
        contribution = "contribution"

    body = (f"Hey @{post.author}\n"
            "**Thanks for contributing on Utopian**.\n")

    # If staff picked add text
    if staff_picked:
        body += ("Congratulations! Your contribution was Staff Picked to "
                 f"receive a maximum vote for the {category} category on "
                 "Utopian for being of significant value to the project and "
                 "the open source community.\n\n")

    body += (f"We’re already looking forward to your next {contribution}!\n\n"
             "**Want to chat? Join us on Discord https://discord.gg/h52nFrV.**"
             "\n\n<a href='https://v2.steemconnect.com/sign/account-witness-v"
             "ote?witness=utopian-io&approve=1'>Vote for Utopian Witness!</a>")

    logger.info(f"Commenting on {post.authorperm} - {body}")
    try:
        post.reply(body, author=ACCOUNT)
    except Exception as comment_error:
        logger.error(comment_error)


def valid_age(post):
    """
    Checks if post is within last twelve hours before payout.
    """
    if post.time_elapsed() > timedelta(hours=156):
        return False
    return True


def valid_translation(post):
    """
    Checks if a translation has the correct beneficiaries set.
    """
    if post.json()["beneficiaries"] == CORRECT_BENEFICIARIES:
        return True


def update_sheet(row, previous, current, vote_status):
    # Just in case sheet was updated in the meantime
    previous_reviewed = sheet.worksheet(title_previous)
    current_reviewed = sheet.worksheet(title_current)
    # Update row depending on which sheet it's in
    if row in previous:
        row_index = previous.index(row) + 1
        previous_reviewed.update_cell(row_index, 10, vote_status)
    elif row in current:
        row_index = current.index(row) + 1
        current_reviewed.update_cell(row_index, 10, vote_status)


def vote_update(row, previous, current, staff_picked=False):
    """
    Upvotes the highest priority contribution and updates the spreadsheet.
    """
    url = row[2]
    category = row[4]

    account = Account(ACCOUNT)
    # Check if post was staff picked
    if staff_picked:
        vote_pct = MAX_VOTE[category]
    else:
        try:
            vote_pct = float(row[-1])
        except ValueError as error:
            logger.error(f"{url} giving error: {error}")
            return

    if vote_pct > 40:
        logger.info("Someone put a voting percentage higher than 40!")
        return

    try:
        post = Comment(url, steem_instance=steem)
        # Check if actually voted on post
        votes = [vote["voter"] for vote in post.json()["active_votes"]]
        logger.info(f"Voting on {post.authorperm} with {vote_pct}%")
        # If in last twelve hours before payout don't vote
        if valid_age(post):
            allows_curation = post.json()["allow_curation_rewards"]

            # Already voted on
            if ACCOUNT in votes:
                logger.error(f"ALREADY VOTED ON: {url}")
                update_sheet(row, previous, current, "Already voted on!")
            # Curation rewards turned off
            elif not allows_curation:
                logger.error(f"DOES NOT ALLOW CURATION REWARDS: {url}")
                update_sheet(row, previous, current, "Doesn't allow curation!")
            # Wrong beneficiaries set
            elif category == "translations" and not valid_translation(post):
                logger.error(f"WRONG BENEFICIARIES: {url}")
                update_sheet(row, previous, current, "Beneficiaries wrong!")
            # Everything okay, so vote!
            else:
                post.vote(vote_pct, account=account)
                bot_comment(post, category, account, staff_picked)
                update_sheet(row, previous, current, "Yes")
        else:
            update_sheet(row, previous, current, "EXPIRED")
    except Exception as vote_error:
        logger.error(vote_error)


def main():
    """
    If voting power is 99.75 then it votes on the contribution with the highest
    score.
    """
    voting_power = Account(ACCOUNT).get_voting_power()
    logger.info(f"Current voting power: {voting_power}")
    if voting_power < 99.75:
        return

    previous = previous_reviewed.get_all_values()
    current = current_reviewed.get_all_values()
    rows = previous[1:] + current[1:]

    # Sort rows by score
    sorted_rows = sorted(rows, key=lambda x: float(x[5]), reverse=True)

    # Check if there's a staff picked contribution
    for row in sorted_rows:
        voted_for = row[-2].lower()
        staff_picked = row[6].lower()
        if voted_for == "pending" and staff_picked == "yes":
            url = row[2]
            post = Comment(url, steem_instance=steem)
            if post.time_elapsed() > timedelta(hours=MINIMUM_AGE):
                vote_update(row, previous, current, True)
                return

    # Otherwise check for pending contribution with highest score
    for row in sorted_rows:
        voted_for = row[-2].lower()
        if voted_for != "pending":
            continue

        url = row[2]
        post = Comment(url, steem_instance=steem)
        if post.time_elapsed() > timedelta(hours=MINIMUM_AGE):
            vote_update(row, previous, current)
            return

    logger.info(f"No eligible posts older than {MINIMUM_AGE} hours found.")

if __name__ == '__main__':
    main()
