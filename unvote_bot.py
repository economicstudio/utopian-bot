from beem.account import Account
from beem.comment import Comment, RecentReplies
from datetime import timedelta
import constants
import json
import os
import time


def get_replies(post):
    """
    Gets all replies to the given post.
    """
    url = f"{post.category}/{post.authorperm}"
    return constants.STEEM.rpc.get_state(url)["content"].keys()


def update_comment(post):
    """
    Updates the comment left by the bot to reflect that the contribution was
    unvoted.
    """
    body = constants.COMMENT_UNVOTE.format(post.author)

    # Iterate over replies until bot's comment is found
    for comment in get_replies(post):
        comment = Comment(comment)
        if comment.author == constants.ACCOUNT and comment.is_comment():
            try:
                constants.LOGGER.info(f"Updating comment {comment.authorperm}")
                comment.edit(body, replace=True)
            except Exception as error:
                constants.LOGGER.error(error)
            return


def unvote_post(row, previous, current):
    """
    Unvotes the given post and updates the spreadsheet to reflect this.
    """
    url = row[2]
    account = Account(constants.ACCOUNT)
    post = Comment(url, steem_instance=constants.STEEM)

    votes = [vote["voter"] for vote in post.json()["active_votes"]]
    if constants.ACCOUNT not in votes:
        constants.LOGGER.info(f"Never voted on {url} in the first place!")
        return

    # Unvote the post
    try:
        constants.LOGGER.info(f"Unvoting {url}")
        post.vote(0, account=account)
        time.sleep(3)
        update_comment(post)
    except Exception as error:
        constants.LOGGER.error(error)

    previous_reviewed = constants.SHEET.worksheet(constants.TITLE_PREVIOUS)
    current_reviewed = constants.SHEET.worksheet(constants.TITLE_CURRENT)

    if row in previous:
        row_index = previous.index(row) + 1
        previous_reviewed.update_cell(row_index, 10, "Unvoted")
        previous_reviewed.update_cell(row_index, 11, 0)
    elif row in current:
        row_index = current.index(row) + 1
        current_reviewed.update_cell(row_index, 10, "Unvoted")
        current_reviewed.update_cell(row_index, 11, 0)


def main():
    """
    Checks if post's score has been changed to zero and unvotes it if
    necessary.
    """
    # Get data from both the current sheet and previous one
    previous = constants.PREVIOUS_REVIEWED.get_all_values()
    current = constants.CURRENT_REVIEWED.get_all_values()
    reviewed = previous[1:] + current[1:]

    # If file already exists compare with current data
    if os.path.isfile(f"{constants.DIR_PATH}/reviews.json"):
        with open(f"{constants.DIR_PATH}/reviews.json") as fd:
            data = json.load(fd)
        for row in reviewed:
            # Row has been changed
            if row not in data:
                voted_on = row[-2]
                score = float(row[5])
                # Only unvote posts with score 0 that have been voted on
                if score == 0 and voted_on == "Yes":
                    unvote_post(row, previous, current)

    # Save current data
    with open(f"{constants.DIR_PATH}/reviews.json", "w") as fd:
        json.dump(reviewed, fd, indent=4)

if __name__ == '__main__':
    main()
