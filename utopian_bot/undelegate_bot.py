from beem import Steem
from beem.account import Account
from datetime import datetime
from dateutil.parser import parse
import logging
import os

# Beem
steem = Steem()
ACCOUNT = "utopian.signup"

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


def get_delegations(limit):
    return steem.rpc.get_vesting_delegations(ACCOUNT, 0, limit)


def main():
    account = Account(ACCOUNT)
    today = datetime.today()
    for delegation in get_delegations(1000):
        min_delegation_time = parse(delegation["min_delegation_time"])
        delegatee = delegation["delegatee"]
        # Check if delegation should be withdrawn
        if today > min_delegation_time:
            logger.info(f"Undelegating from {delegatee}")
            account.delegate_vesting_shares(delegatee, "0", ACCOUNT)

if __name__ == '__main__':
    main()
