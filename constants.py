from beem import Steem
from datetime import date, datetime, timedelta
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import logging
import os

# Get path of current folder
DIR_PATH = os.path.dirname(os.path.realpath(__file__))

# The minimum age a post must be to receive an upvote
MIN_AGE = 24

# Logging
LOGGER = logging.getLogger("utopian-io")
LOGGER.setLevel(logging.INFO)
FILE_HANDLER = logging.FileHandler(f"{DIR_PATH}/bot.log")
FILE_HANDLER.setLevel(logging.DEBUG)
FORMATTER = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
FILE_HANDLER.setFormatter(FORMATTER)
LOGGER.addHandler(FILE_HANDLER)

# Beem
STEEM = Steem()

# Accounts
ACCOUNT = "utopian-io"

# Spreadsheet variables
SCOPE = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]
CREDENTIALS = ServiceAccountCredentials.from_json_keyfile_name(
    f"{DIR_PATH}/client_secret.json", SCOPE)
CLIENT = gspread.authorize(CREDENTIALS)
SHEET = CLIENT.open("Utopian Reviews")

# Get date of current, next and previous Thursday
TODAY = date.today()
OFFSET = (TODAY.weekday() - 3) % 7
THIS_WEEK = TODAY - timedelta(days=OFFSET)
LAST_WEEK = THIS_WEEK - timedelta(days=7)
NEXT_WEEK = THIS_WEEK + timedelta(days=7)

# Get title's of most recent two worksheets
TITLE_PREVIOUS = f"Reviewed - {LAST_WEEK:%b %-d} - {THIS_WEEK:%b %-d}"
TITLE_CURRENT = f"Reviewed - {THIS_WEEK:%b %-d} - {NEXT_WEEK:%b %-d}"
PREVIOUS_REVIEWED = SHEET.worksheet(TITLE_PREVIOUS)
CURRENT_REVIEWED = SHEET.worksheet(TITLE_CURRENT)

# Max votes per category
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

# Beneficiaries
DAVINCI_BENEFICIARY = {
    "account": "davinci.pay",
    "weight": 1000
}
UTOPIAN_BENEFICIARY = {
    "account": "utopian.pay",
    "weight": 500
}

# Comment text
COMMENT_HEADER = "Hey, @{}!\n\n**Thanks for contributing on Utopian**.\n"

COMMENT_STAFF_PICK = (
    "Congratulations! Your contribution was Staff Picked to receive a maximum "
    "vote for the {} category on Utopian for being of significant value to "
    "the project and the open source community.\n\n")

COMMENT_FOOTER = (
    "We’re already looking forward to your next {}!\n\n"
    "**Get higher incentives and support Utopian.io!**\n Simply set "
    "@utopian.pay as a 5% (or higher) payout beneficiary on your contribution "
    "post (via [SteemPlus](https://chrome.google.com/webstore/detail/steemplus"
    "/mjbkjgcplmaneajhcbegoffkedeankaj?hl=en) or [Steeditor](https://steeditor"
    ".app)).\n\n**Want to chat? Join us on Discord "
    "https://discord.gg/h52nFrV.**\n\n<a href='https://steemconnect.com/sign/"
    "account-witness-vote?witness=utopian-io&approve=1'>Vote for Utopian "
    "Witness!</a>")

COMMENT_UNVOTE = (
    "Hey @{}, your contribution was unvoted because we found out that it did "
    "not follow the [Utopian guidelines](https://join.utopian.io/guidelines). "
    "\n\n Upvote this comment to help Utopian grow its power and help other "
    "Open Source contributions like this one.\n\n**Want to chat? Join us on "
    "[Discord](https://discord.gg/h52nFrV).**")

COMMENT_PATTERN = "Chat with us on [Discord]"

# Category points
CATEGORY_POINTS = {
    "ideas": 6.0,
    "development": 10.0,
    "graphics": 8.0,
    "bug-hunting": 7.0,
    "analysis": 8.0,
    "social": 5.0,
    "video-tutorials": 8.0,
    "tutorials": 8.0,
    "copywriting": 5.0,
    "documentation": 5.0,
    "blog": 6.0,
    "translations": 8.0
}


# Review comment
COMMENT_REVIEW = (
    "Thank you for your review, @{}!\n\nSo far this week you've reviewed {} "
    "contributions. Keep up the good work!")

MODERATOR_WAIT = 48
