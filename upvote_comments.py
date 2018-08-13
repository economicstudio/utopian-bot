from beem.account import Account
from beem.comment import Comment
from contribution import Contribution
from upvote_bot import review_vote
import constants


def main():
    """
    Upvotes all of the currently pending review comments.
    """
    current = constants.CURRENT_REVIEWED.get_all_values()
    contributions = [Contribution(contribution) for contribution in current]
    for contribution in contributions:
        if contribution.review_status.lower() == "pending":
            current = constants.CURRENT_REVIEWED.get_all_values()
            review_vote(current)


if __name__ == '__main__':
    main()
