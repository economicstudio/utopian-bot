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
ACCOUNT = "amosbastian"

# Spreadsheet variables
SCOPE = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]
CREDENTIALS = ServiceAccountCredentials.from_json_keyfile_name(
    f"{DIR_PATH}/client_secret.json", SCOPE)
CLIENT = gspread.authorize(CREDENTIALS)
SHEET = CLIENT.open("Copy of Utopian Reviews")

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
COMMENT_HEADER = "Hey @{}\n **Thanks for contributing on Utopian**.\n"

COMMENT_STAFF_PICK = (
    "Congratulations! Your contribution was Staff Picked to receive a maximum "
    "vote for the {} category on Utopian for being of significant value to "
    "the project and the open source community.\n\n")

COMMENT_FOOTER = (
    "We’re already looking forward to your next {}!\n\n**Want to chat? Join "
    "us on Discord https://discord.gg/h52nFrV.**\n\n<a href='https://v2.steemc" 
    "onnect.com/sign/account-witness-vote?witness=utopian-io&approve=1'>Vote "
    "for Utopian Witness!</a>")

COMMENT_UNVOTE = (
    "Hey @{}, your contribution was unvoted because we found out that it did "
    "not follow the [Utopian guidelines](https://join.utopian.io/guidelines). "
    "\n\n Upvote this comment to help Utopian grow its power and help other "
    "Open Source contributions like this one.\n\n**Want to chat? Join us on "
    "[Discord](https://discord.gg/h52nFrV).**")

# Category points
CATEGORY_POINTS = {
    "ideas": 4.0,
    "development": 8.5,
    "graphics": 6.0,
    "bug-hunting": 6.5,
    "analysis": 6.5,
    "social": 4.0,
    "video-tutorials": 8.0,
    "tutorials": 8.0,
    "copywriting": 4.0,
    "documentation": 4.5,
    "blog": 4.5,
    "translations": 8.0
}
TASK_REQUEST = 2.5

# Review comment
COMMENT_MATCH = (
    "Need help? Write a ticket on https://support.utopian.io/.")

COMMENT_ROW = (
    "Hi!")
