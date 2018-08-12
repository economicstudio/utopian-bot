from beem.account import Account
from beem.comment import Comment
from contribution import Contribution
from datetime import timedelta
from dateutil.parser import parse
import constants
import requests
import time


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


def update_sheet(row, vote_status, contribution=True):
    """
    Updates the row in one of the eligible worksheets.
    """
    row = list(row.__dict__.values())
    previous, current, _ = get_rows()

    if contribution:
        column_index = 11
    else:
        column_index = 10

    previous_reviewed = constants.SHEET.worksheet(constants.TITLE_PREVIOUS)
    current_reviewed = constants.SHEET.worksheet(constants.TITLE_CURRENT)

    if row in previous:
        row_index = previous.index(row) + 1
        previous_reviewed.update_cell(row_index, column_index, vote_status)
    elif row in current:
        row_index = current.index(row) + 1
        current_reviewed.update_cell(row_index, column_index, vote_status)


def max_weight(category):
    """
    Returns the max voting percentage of the given category.
    """
    try:
        weight = constants.MAX_VOTE[category]
    except KeyError:
        weight = constants.MAX_TASK_REQUEST
    return weight


def update_weight(weight):
    """
    Updates the voting percentage if beneficiaries utopian.pay set.
    """
    weight = float(weight)
    utopian_weight = constants.UTOPIAN_BENEFICIARY["weight"]
    return weight + 0.1 * weight + utopian_weight / 100.0 + 1.0


def vote_update(row, staff_picked=False):
    """
    Upvotes the highest priority contribution and updates the spreadsheet.
    """
    url = row.url
    category = row.category
    account = Account(constants.ACCOUNT)

    # Check if post was staff picked
    if staff_picked:
        weight = max_weight(category)
    else:
        weight = float(row.weight)

    try:
        post = Comment(url, steem_instance=constants.STEEM)
        
        # If in last twelve hours before payout don't vote
        if not valid_age(post):
            constants.LOGGER.error(f"In last 12 hours before payout: {url}")
            update_sheet(row, "EXPIRED")
            return

        # Already voted on
        votes = [vote["voter"] for vote in post.json()["active_votes"]]
        if constants.ACCOUNT in votes:
            constants.LOGGER.error(f"Already voted on: {url}")
            update_sheet(row, "Already voted on!")
            return

        # Curation rewards turned off
        allows_curation = post.json()["allow_curation_rewards"]
        if not allows_curation:
            constants.LOGGER.error(f"Does not allow curation rewards: {url}")
            update_sheet(row, "Doesn't allow curation!")
            return
        
        # Wrong translation beneficiaries set
        if category == "translations" and not valid_translation(post):
            constants.LOGGER.error(f"Wrong translation beneficiaries: {url}")
            update_sheet(row, "Beneficiaries wrong!")
            return
        
        # Voting % higher than possible
        if weight > max_weight(category):
            constants.LOGGER.error(f"Voting % exceeds max: {url}")
            update_sheet(row, "Voting percentage exceeds max!")
            return
        
        beneficiary_set = beneficiary(post)
        if beneficiary_set:
            weight = update_weight(weight)

        constants.LOGGER.info(f"Voting on {post.authorperm} with {weight}%")
        # post.vote(weight, account=account)
        # bot_comment(post, category, staff_picked)
        update_sheet(row, "Yes")
    except Exception as vote_error:
        constants.LOGGER.error(vote_error)


def get_rows():
    """
    Return all the rows in the most recent two review worksheets.
    """
    previous = constants.PREVIOUS_REVIEWED.get_all_values()
    current = constants.CURRENT_REVIEWED.get_all_values()
    rows = previous[1:] + current[1:]
    return previous, current, rows


def points_to_weight(account, points):
    """
    Returns the voting weight needed for a vote worth the points equivalence
    in SBD.
    """
    max_SBD = account.get_voting_value_SBD()
    return 100 * points / max_SBD


def handle_comment(contribution):
    """
    Finds the moderator's comment in response to the contribution then upvotes
    and replies to it.
    """
    post = Comment(contribution.url)
    for reply in post.get_replies():
        if reply.author == contribution.moderator:
            if not constants.COMMENT_MATCH in reply.body:
                return False
            account = Account(constants.ACCOUNT)
            
            try:
                points = constants.CATEGORY_POINTS[contribution.category]
            except KeyError:
                points = constants.TASK_REQUEST
            
            weight = points_to_weight(account, points)
            
            try:
                # reply.vote(weight, account=account)
                constants.LOGGER.info(f"Handling comment: {reply.authorperm}")
                return True
            except Exception as error:
                constants.LOGGER.error(f"Handle comment error: {error}")
                return False
            
            break


def review_vote():
    """
    Finds the first review comment waiting to be upvoted and tries upvoting it.
    """
    current = constants.CURRENT_REVIEWED.get_all_values()
    for row in current:
        contribution = Contribution(row)
        if contribution.review_status.lower() == "pending":
            try:
                is_handled = handle_comment(contribution)
                print(is_handled)
                if is_handled:
                    update_sheet(contribution, "Yes", False)
                    time.sleep(20)
            except Exception as error:
                constants.LOGGER.error(f"Review vote error: {error}")
            
            break
            

def main():
    """
    If voting power is > 99.75 then it votes on the oldest contribution
    currently pending and a review comment made be a moderator.
    """
    voting_power = Account(constants.ACCOUNT).get_voting_power()
    
    constants.LOGGER.info(f"Current voting power: {voting_power}")
    # if voting_power < 99.75:
        # return

    review_vote()
    _, _, rows = get_rows()

    response = requests.get("https://utopian.rocks/api/posts?status=pending")
    if len(response.json()) == 0:
        constants.LOGGER.info(f"No pending contributions found in the queue.")
        return

    pending = sorted(response.json(), key=lambda x: x["created"]["$date"])

    for contribution in pending:
        for row in rows:
            row = Contribution(row)
            if row.vote_status.lower() != "pending":
                continue

            # Contribution found in spreadsheet
            if row.url == contribution["url"]:
                post = Comment(row.url, steem_instance=constants.STEEM)
                if post.time_elapsed() > timedelta(hours=constants.MIN_AGE):
                    if row.staff_pick.lower() == "yes":
                        vote_update(row, True)
                    else:
                        vote_update(row)
                    return

if __name__ == '__main__':
    main()
