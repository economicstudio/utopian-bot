from datetime import date, datetime, timedelta
import logging
import gspread
from beem import Steem
from beem.account import Account
from beem.comment import Comment
from dateutil.parser import parse
from oauth2client.service_account import ServiceAccountCredentials

# Logging
logger = logging.getLogger("utopian-io")
logger.setLevel(logging.INFO)
fh = logging.FileHandler("/root/utopian-bot/bot.log")
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
fh.setFormatter(formatter)
logger.addHandler(fh)

# Beem
steem = Steem()

# Spreadsheet variables
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name(
    "/root/utopian-bot/client_secret.json", scope)
client = gspread.authorize(credentials)
sheet = client.open("Copy of Utopian Reviews")
today = date.today()
offset = (today.weekday() - 3) % 7
this_week = today - timedelta(days=offset)
next_week = this_week + timedelta(days=7)
title_reviewed = f"Reviewed - {this_week:%b %-d} - {next_week:%b %-d}"
reviewed = sheet.worksheet(title_reviewed)

MAX_VOTE = {
    "ideas": 5.0,
    "development": 30.0,
    "bug-hunting": 8.0,
    "translations": 20.0,
    "graphics": 25.0,
    "analysis": 25.0,
    "social": 15.0,
    "documentation": 15.0,
    "tutorials": 15.0,
    "video-tutorials": 20.0,
    "copywriting": 15.0,
    "blog": 15.0,
}


def get_current_vp(username):
    """
    Get an account's current voting power. Credit to @emrebeyler.
    """
    account = Account(username)
    last_vote_time = account["last_vote_time"].replace(tzinfo=None)
    diff_in_seconds = (datetime.utcnow() - last_vote_time).total_seconds()
    regenerated_vp = diff_in_seconds * 10000 / 86400 / 5
    total_vp = (account["voting_power"] + regenerated_vp) / 100
    if total_vp > 100:
        total_vp = 100

    logger.info(f"Current voting power: {total_vp}")
    return total_vp


def bot_comment(post, category, account, staff_picked=False):
    """
    Comments on the given post. Content changes depending on the category and
    if the post was staff picked or not.
    """
    if "task" in category:
        contribution = "task request"
    else:
        contribution = "contribution"

    body = (f"Hey @{post.author}\n"
            "**Thanks for contributing on Utopian**.\n")

    if staff_picked:
        body += ("Congratulations! Your contribution was Staff Picked to "
                 f"receive a maximum vote for the {category} category on "
                 "Utopian for being of significant value to the project and "
                 "the open source community.\n\n")

    body += (f"We’re already looking forward to your next {contribution}!\n\n"
             "**Contributing on Utopian**\n"
             "Learn how to contribute on "
             "<a href='https://join.utopian.io'>our website</a> or by watching"
             " <a href='https://www.youtube.com/watch?v=8S1AtrzYY1Q'>this "
             "tutorial</a> on Youtube.\n\n"
             "**Want to chat? Join us on Discord https://discord.gg/h52nFrV.**"
             "\n\n<a href='https://v2.steemconnect.com/sign/account-witness-v"
             "ote?witness=utopian-io&approve=1'>Vote for Utopian Witness!</a>")

    logger.info(f"Commenting on {post.authorperm} - {body}")
    #try:
    #    post.reply("Cool post!", author="amosbastian")
    #except Exception as comment_error:
    #    logger.error(comment_error)


def vote_update(row, row_index, staff_picked=False):
    """
    Upvotes the highest priority contribution and updates the spreadsheet.
    """
    url = row[2]
    category = row[4]

    account = Account("amosbastian")
    if staff_picked:
        vote_pct = MAX_VOTE[category]
    else:
        vote_pct = float(row[-1])

    try:
        post = Comment(url, steem_instance=steem)
        logger.info(f"Voting on {post.authorperm} with {vote_pct}%")
        post.vote(vote_pct, account=account)
        bot_comment(post, category, account, staff_picked)
        reviewed.update_cell(row_index, 10, "Yes")
    except Exception as vote_error:
        logger.error(vote_error)


def main():
    """
    If voting power is 99 then it votes on one contribution
    """
    voting_power = get_current_vp("amosbastian")
    rows = reviewed.get_all_values()

    # Sort rows by score
    sorted_rows = sorted(rows[1:], key=lambda x: float(x[-1]), reverse=True)

    if voting_power < 99:
        return

    # Check if there's a staff picked contribution
    for row in sorted_rows:
        voted_for = row[-2]
        staff_picked = row[6]
        if voted_for == "Pending" and staff_picked == "Yes":
            vote_update(row, rows.index(row) + 1, True)
            return

    # Otherwise check for pending contribution with highest score
    for row in sorted_rows:
        voted_for = row[-2]
        if voted_for != "Pending":
            continue

        vote_update(row, rows.index(row) + 1)
        return


if __name__ == '__main__':
    main()
