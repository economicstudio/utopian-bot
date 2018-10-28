import logging
import os
from datetime import date, datetime, timedelta

import gspread
from beem import Steem
from oauth2client.service_account import ServiceAccountCredentials
from watson_developer_cloud import NaturalLanguageUnderstandingV1

DIR_PATH = os.path.dirname(os.path.realpath(__file__))
LOGGING = True
LOGGER = logging.getLogger("utopian-io")
LOGGER.setLevel(logging.INFO)
FILE_HANDLER = logging.FileHandler(f"{DIR_PATH}/bot.log")
FILE_HANDLER.setLevel(logging.DEBUG)
FORMATTER = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
FILE_HANDLER.setFormatter(FORMATTER)
LOGGER.addHandler(FILE_HANDLER)

STEEM = Steem()
ACCOUNT = "utopian-io"

SCOPE = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]
CREDENTIALS = ServiceAccountCredentials.from_json_keyfile_name(
    f"{DIR_PATH}/client_secret.json", SCOPE)
CLIENT = gspread.authorize(CREDENTIALS)
SHEET = CLIENT.open("Utopian Reviews")

TODAY = date.today()
OFFSET = (TODAY.weekday() - 3) % 7
THIS_WEEK = TODAY - timedelta(days=OFFSET)
LAST_WEEK = THIS_WEEK - timedelta(days=7)
NEXT_WEEK = THIS_WEEK + timedelta(days=7)

TITLE_PREVIOUS = f"Reviewed - {LAST_WEEK:%b %-d} - {THIS_WEEK:%b %-d}"
TITLE_CURRENT = f"Reviewed - {THIS_WEEK:%b %-d} - {NEXT_WEEK:%b %-d}"
PREVIOUS_REVIEWED = SHEET.worksheet(TITLE_PREVIOUS)
CURRENT_REVIEWED = SHEET.worksheet(TITLE_CURRENT)

CATEGORY_WEIGHTING = {
    "ideas": 10.0,
    "development": 10.0,
    "bug-hunting": 10.0,
    "translations": 10.0,
    "graphics": 10.0,
    "analysis": 10.0,
    "social": 10.0,
    "documentation": 10.0,
    "tutorials": 10.0,
    "video-tutorials": 10.0,
    "copywriting": 10.0,
    "blog": 10.0,
    "anti-abuse": 10.0,
    "task-request": 10.0,
    "iamutopian": 10.0,
}

MODERATION_REWARD = {
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
    "translations": 8.0,
    "iamutopian": 6.0,
    "anti-abuse": 6.0,
    "task-request": 2.5,
}

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
COMMENT_REVIEW = (
    "Thank you for your review, @{}! Keep up the good work!")

CONTRIBUTION_BATCH = "https://utopian.rocks/api/batch/contributions"
COMMENT_BATCH = "https://utopian.rocks/api/batch/comments"
VP_TOTAL = 18.0
VP_COMMENTS = 3.2

WATSON_SERVICE = NaturalLanguageUnderstandingV1(
    version="2018-03-16",
    username=os.environ["WATSON_USERNAME"],
    password=os.environ["WATSON_PASSWORD"]
)
WATSON_LABELS = [
    "/science/biology/biotechnology",
    "/science/biology/botany",
    "/science/biology/breeding",
    "/science/biology/cytology",
    "/science/biology/marine biology",
    "/science/biology/molecular biology",
    "/science/biology/zoology/endangered species",
    "/science/biology/zoology/entomology",
    "/science/biology/zoology/ornithology",
    "/science/biology/zoology",
    "/science/chemistry/organic chemistry",
    "/science/chemistry",
    "/science/computer science/artificial intelligence",
    "/science/computer science/cryptography",
    "/science/computer science/distributed systems",
    "/science/computer science/information science",
    "/science/computer science/software engineering",
    "/science/computer science",
    "/science/ecology/environmental disaster",
    "/science/ecology/pollution",
    "/science/ecology/waste management/recycling",
    "/science/ecology/waste management/waste disposal",
    "/science/ecology",
    "/science/engineering",
    "/science/geography/cartography",
    "/science/geography/topography",
    "/science/geography",
    "/science/geology/mineralogy",
    "/science/geology/seismology/earthquakes",
    "/science/geology/volcanology/volcanic eruptions",
    "/science/geology",
    "/science/mathematics/algebra",
    "/science/mathematics/arithmetic",
    "/science/mathematics/geometry",
    "/science/mathematics/statistics",
    "/science/mathematics",
    "/science/medicine/cardiology",
    "/science/medicine/dermatology",
    "/science/medicine/embryology",
    "/science/medicine/genetics",
    "/science/medicine/immunology",
    "/science/medicine/medical research",
    "/science/medicine/oncology",
    "/science/medicine/orthopedics",
    "/science/medicine/pediatrics",
    "/science/medicine/pharmacology",
    "/science/medicine/physiology",
    "/science/medicine/psychology and psychiatry/psychoanalysis",
    "/science/medicine/psychology and psychiatry",
    "/science/medicine/surgery/cosmetic surgery",
    "/science/medicine/surgery/transplants",
    "/science/medicine/surgery",
    "/science/medicine/veterinary medicine",
    "/science/medicine",
    "/science/physics/atomic physics",
    "/science/physics/astrophysics",
    "/science/physics/electromagnetism",
    "/science/physics/hydraulics",
    "/science/physics/nanotechnology",
    "/science/physics/optics",
    "/science/physics/space and astronomy",
    "/science/physics/thermodynamics",
    "/science/physics",
    "/business and industrial/aerospace and defense/space technology",
    "/business and industrial/automation/robotics",
    "/business and industrial/business software",
    "/business and industrial/energy/electricity",
    "/hobbies and interests/inventors and patents",
    "/science",
    "/technology and computing/computer security/antivirus and malware",
    "/technology and computing/computer security/network security",
    "/technology and computing/computer security",
    "/technology and computing/data centers",
    "/technology and computing/electronic components",
    "/technology and computing/enterprise technology/data management",
    "/technology and computing/enterprise technology/enterprise resource planning",
    "/technology and computing/hardware/computer/servers",
    "/technology and computing/hardware/computer components/chips and processors",
    "/technology and computing/hardware/computer/components/disks",
    "/technology and computing/hardware/computer/components/graphics cards",
    "/technology and computing/hardware/computer/components/memory/portable",
    "/technology and computing/hardware/computer/components/memory",
    "/technology and computing/hardware/computer/components/motherboards",
    "/technology and computing/hardware/computer/networking/wireless technology",
    "/technology and computing/hardware",
    "/technology and computing/internet technology/isps",
    "/technology and computing/internet technology/social network",
    "/technology and computing/internet technology/web design and html",
    "/technology and computing/internet technology/web search/people search",
    "/technology and computing/internet technology/web search",
    "/technology and computing/internet technology",
    "/technology and computing/networking/network monitoring and management",
    "/technology and computing/networking/vpn and remote access",
    "/technology and computing/networking",
    "/technology and computing/operating systems/linux",
    "/technology and computing/operating systems/mac os",
    "/technology and computing/operating systems/unix",
    "/technology and computing/operating systems/windows",
    "/technology and computing/operating systems",
    "/technology and computing/programming languages/c and c++",
    "/technology and computing/programming languages/java",
    "/technology and computing/programming languages/javascript",
    "/technology and computing/programming languages/visual basic",
    "/technology and computing/programming languages",
    "/technology and computing/software/databases",
    "/technology and computing/software/desktop publishing",
    "/technology and computing/software/desktop video",
    "/technology and computing/software/graphics software/animation",
    "/technology and computing/software/graphics software",
    "/technology and computing/software/net conferencing",
    "/technology and computing/software/shareware and freeware",
    "/technology and computing/technological innovation"
]
TRAIL_ACCOUNTS = {
    "steemstem": {
        "check_context": False,
        "whitelisted": True,
        "weight_multiplier": 0.40,
        "max_weight": 4000,
        "comment": ("#### Hi @{}!\n\nYour post was upvoted by Utopian.io in "
                    "cooperation with @{} - supporting knowledge, "
                    "innovation and technological advancement on the Steem "
                    "Blockchain.\n\n#### Contribute to Open Source with "
                    "utopian.io\nLearn how to contribute on <a href='https://j"
                    "oin.utopian.io'>our website</a> and join the new open "
                    "source economy.\n\n**Want to chat? Join the Utopian "
                    "Community on Discord https://discord.gg/h52nFrV**"),
        "weight_trigger": 6000,
        "upvote_limit": 1000,
        "is_priority": False,
    },
    "steemmakers": {
        "check_context": True,
        "whitelisted": False,
        "weight_multiplier": 0.05,
        "max_weight": 500,
        "comment": ("#### Hi @{}!\n\nYour post was upvoted by Utopian.io in "
                    "cooperation with @{} - supporting knowledge, "
                    "innovation and technological advancement on the Steem "
                    "Blockchain.\n\n#### Contribute to Open Source with "
                    "utopian.io\nLearn how to contribute on <a href='https://j"
                    "oin.utopian.io'>our website</a> and join the new open "
                    "source economy.\n\n**Want to chat? Join the Utopian "
                    "Community on Discord https://discord.gg/h52nFrV**"),
        "weight_trigger": 1,
        "upvote_limit": 1000,
        "is_priority": False,
    },
    "msp_waves": {
        "check_context": False,
        "whitelisted": False,
        "weight_multiplier": 1.0,
        "max_weight": 5000,
        "comment": ("#### Hi @{}!\n\nYour post was upvoted by Utopian.io in "
                    "cooperation with @{} - supporting knowledge, "
                    "innovation and technological advancement on the Steem "
                    "Blockchain.\n\n#### Contribute to Open Source with "
                    "utopian.io\nLearn how to contribute on <a href='https://j"
                    "oin.utopian.io'>our website</a> and join the new open "
                    "source economy.\n\n**Want to chat? Join the Utopian "
                    "Community on Discord https://discord.gg/h52nFrV**"),
        "weight_trigger": 1,
        "upvote_limit": 1,
        "is_priority": True,
    }
}
WATSON_SCORE = 0.68
