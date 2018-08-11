from beem.account import Account
from beem.comment import Comment
from datetime import timedelta
from dateutil.parser import parse
import constants
import requests


def bot_comment(post, category, staff_picked=False):
    """
    Comments on the given post. Content changes depending on the category and
    if the post was staff picked or not.
    """
    # Change text depending on if contribution is task request or not
    if "task" in category:
        contribution = "task request"
    else:
        contribution = "contribution"

    body = constants.COMMENT_HEADER.format(post.author)

    # If staff picked add text
    if staff_picked:
        body += constants.COMMENT_STAFF_PICK.format(category)

    body += constants.COMMENT_FOOTER.format(contribution)

    constants.LOGGER.info(f"Commenting on {post.authorperm} - {body}")
    try:
        post.reply(body, author=constants.ACCOUNT)
    except Exception as comment_error:
        constants.LOGGER.error(comment_error)


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
    if (constants.DAVINCI_BENEFICIARY in post.json()["beneficiaries"] and
        constants.UTOPIAN_BENEFICIARY in post.json()["beneficiaries"]):
        return True
    return False


def beneficiary(post):
    """
    Checks if utopian.pay set as 5% beneficiary
    """
    if (constants.UTOPIAN_BENEFICIARY in post.json()["beneficiaries"]):
        return True
    return False


def update_sheet(row, previous, current, vote_status):
    """
    Updates the row in one of the eligible worksheets.
    """
    previous_reviewed = constants.SHEET.worksheet(constants.TITLE_PREVIOUS)
    current_reviewed = constants.SHEET.worksheet(constants.TITLE_CURRENT)

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
        vote_pct = constants.MAX_VOTE[category]
    except KeyError:
        vote_pct = constants.MAX_TASK_REQUEST
    return vote_pct


def update_pct(vote_pct):
    """
    Updates the voting percentage if beneficiaries utopian.pay set.
    """
    vote_pct = float(vote_pct)
    utopian_weight = constants.UTOPIAN_BENEFICIARY["weight"]
    return vote_pct + 0.1 * vote_pct + utopian_weight / 100.0 + 1.0


def vote_update(row, previous, current, staff_picked=False):
    """
    Upvotes the highest priority contribution and updates the spreadsheet.
    """
    url = row[2]
    category = row[4]
    account = Account(constants.ACCOUNT)

    # Check if post was staff picked
    if staff_picked:
        vote_pct = max_pct(category)
    else:
        vote_pct = float(row[-1])

    try:
        post = Comment(url, steem_instance=constants.STEEM)
        
        # If in last twelve hours before payout don't vote
        if not valid_age(post):
            constants.LOGGER.error(f"In last 12 hours before payout: {url}")
            update_sheet(row, previous, current, "EXPIRED")
            return

        # Already voted on
        votes = [vote["voter"] for vote in post.json()["active_votes"]]
        if constants.ACCOUNT in votes:
            constants.LOGGER.error(f"Already voted on: {url}")
            update_sheet(row, previous, current, "Already voted on!")
            return

        # Curation rewards turned off
        allows_curation = post.json()["allow_curation_rewards"]
        if not allows_curation:
            constants.LOGGER.error(f"Does not allow curation rewards: {url}")
            update_sheet(row, previous, current, "Doesn't allow curation!")
            return
        
        # Wrong translation beneficiaries set
        if category == "translations" and not valid_translation(post):
            constants.LOGGER.error(f"Wrong translation beneficiaries: {url}")
            update_sheet(row, previous, current, "Beneficiaries wrong!")
            return
        
        # Voting % higher than possible
        if vote_pct > max_pct(category):
            constants.LOGGER.error(f"Voting % exceeds max: {url}")
            update_sheet(
                row, previous, current, "Voting percentage exceeds max!")
            return
        
        beneficiary_set = beneficiary(post)
        if beneficiary_set:
            vote_pct = update_pct(vote_pct)

        constants.LOGGER.info(f"Voting on {post.authorperm} with {vote_pct}%")
        post.vote(vote_pct, account=account)
        bot_comment(post, category, staff_picked)
        update_sheet(row, previous, current, "Yes")
    except Exception as vote_error:
        constants.LOGGER.error(vote_error)


def main():
    """
    If voting power is 99.75 then it votes on the oldest contribution currently
    pending.
    """
    voting_power = Account(constants.ACCOUNT).get_voting_power()
    
    constants.LOGGER.info(f"Current voting power: {voting_power}")
    if voting_power < 99.75:
        return

    previous = constants.PREVIOUS_REVIEWED.get_all_values()
    current = constants.CURRENT_REVIEWED.get_all_values()
    rows = previous[1:] + current[1:]

    response = requests.get("https://utopian.rocks/api/posts?status=pending")
    if len(response.json()) == 0:
        constants.LOGGER.info(f"No pending contributions found in the queue.")
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
                post = Comment(url, steem_instance=constants.STEEM)
                if post.time_elapsed() > timedelta(hours=constants.MINIMUM_AGE):
                    staff_picked = row[6].lower()
                    if staff_picked:
                        vote_update(row, previous, current, True)
                    else:
                        vote_update(row, previous, current)
                    return

if __name__ == '__main__':
    main()
