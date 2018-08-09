from beem import Steem
from beem.account import Account
from beem.comment import Comment
from datetime import date, datetime, timedelta
from dateutil.parser import parse
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import logging
import os
import requests

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
    "ideas": 20.0,
    "development": 55.0,
    "bug-hunting": 13.0,
    "translations": 35.0,
    "graphics": 40.0,
    "analysis": 45.0,
    "social": 30.0,
    "documentation": 30.0,
    "tutorials": 30.0,
    "video-tutorials": 35.0,
    "copywriting": 30.0,
    "blog": 30.0,
}
MAX_TASK_REQUEST = 6.0

DAVINCI_BENEFICIARY = {
    "account": "davinci.pay",
    "weight": 1000
}

UTOPIAN_BENEFICIARY = {
    "account": "utopian.pay",
    "weight": 500
}


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
    if (DAVINCI_BENEFICIARY in post.json()["beneficiaries"] and
        UTOPIAN_BENEFICIARY in post.json()["beneficiaries"]):
        return True
    return False


def beneficiary(post):
    """
    Checks if utopian.pay set as 5% beneficiary
    """
    if (UTOPIAN_BENEFICIARY in post.json()["beneficiaries"]):
        return True
    return False


def update_sheet(row, previous, current, vote_status):
    """
    Updates the row in one of the eligible worksheets.
    """
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


def max_pct(category):
    """
    Returns the max voting percentage of the given category.
    """
    try:
        vote_pct = MAX_VOTE[category]
    except KeyError:
        vote_pct = MAX_TASK_REQUEST
    return vote_pct


def update_pct(vote_pct):
    """
    Updates the voting percentage if beneficiaries utopian.pay set.
    """
    vote_pct = float(vote_pct)
    return vote_pct + 0.1 * vote_pct + UTOPIAN_BENEFICIARY["weight"] / 100.0


def vote_update(row, previous, current, staff_picked=False):
    """
    Upvotes the highest priority contribution and updates the spreadsheet.
    """
    url = row[2]
    category = row[4]
    account = Account(ACCOUNT)

    # Check if post was staff picked
    if staff_picked:
        vote_pct = max_pct(category)
    else:
        vote_pct = float(row[-1])

    try:
        post = Comment(url, steem_instance=steem)
        
        # If in last twelve hours before payout don't vote
        if valid_age(post):
            logger.error(f"In last 12 hours before payout: {url}")
            update_sheet(row, previous, current, "EXPIRED")
            return

        # Already voted on
        votes = [vote["voter"] for vote in post.json()["active_votes"]]
        if ACCOUNT in votes:
            logger.error(f"Already voted on: {url}")
            update_sheet(row, previous, current, "Already voted on!")
            return

        # Curation rewards turned off
        allows_curation = post.json()["allow_curation_rewards"]
        if not allows_curation:
            logger.error(f"Does not allow curation rewards: {url}")
            update_sheet(row, previous, current, "Doesn't allow curation!")
            return
        
        # Wrong translation beneficiaries set
        if category == "translations" and not valid_translation(post):
            logger.error(f"Wrong translation beneficiaries: {url}")
            update_sheet(row, previous, current, "Beneficiaries wrong!")
            return
        
        # Voting % higher than possible
        if vote_pct > max_pct(category):
            logger.error(f"Voting % exceeds max: {url}")
            update_sheet(
                row, previous, current, "Voting percentage exceeds max!")
            return
        
        beneficiary_set = beneficiary(post)
        if beneficiary_set:
            vote_pct = update_pct(vote_pct)

        logger.info(f"Voting on {post.authorperm} with {vote_pct}%")
        post.vote(vote_pct, account=account)
        bot_comment(post, category, account, staff_picked)
        update_sheet(row, previous, current, "Yes")
    except Exception as vote_error:
        logger.error(vote_error)


def main():
    """
    If voting power is 99.75 then it votes on the oldest contribution currently
    pending.
    """
    voting_power = Account(ACCOUNT).get_voting_power()
    
    logger.info(f"Current voting power: {voting_power}")
    if voting_power < 99.75:
        return

    previous = previous_reviewed.get_all_values()
    current = current_reviewed.get_all_values()
    rows = previous[1:] + current[1:]

    response = requests.get("https://utopian.rocks/api/posts?status=pending")
    if len(response.json()) == 0:
        logger.info(f"No eligible posts older than {MINIMUM_AGE} hours found.")
        return

    pending = sorted(response.json(), key=lambda x: x["created"]["$date"])

    for contribution in pending:
        for row in rows:
            voted_for = row[-2].lower()
            if voted_for != "pending":
                continue

            url = row[2]
            # Contribution found in spreadsheet
            if url == contribution["url"]:
                post = Comment(url, steem_instance=steem)
                if post.time_elapsed() > timedelta(hours=MINIMUM_AGE):
                    staff_picked = row[6].lower()
                    if staff_picked:
                        vote_update(row, previous, current, True)
                    else:
                        vote_update(row, previous, current)
                    return

if __name__ == '__main__':
    main()
