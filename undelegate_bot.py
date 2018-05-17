from beem import Steem
from beem.account import Account
from datetime import datetime
from dateutil.parser import parse

# Beem
steem = Steem()
ACCOUNT = "utopian.signup"


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
            account.delegate_vesting_shares(delegatee, "0", ACCOUNT)

if __name__ == '__main__':
    main()
