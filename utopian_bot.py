import json
import time
from datetime import datetime, timedelta
from operator import itemgetter

import numpy as np
import requests
from beem.account import Account
from beem.comment import Comment
from dateutil.parser import parse
from prettytable import PrettyTable

from constants import (ACCOUNT, CATEGORY_WEIGHTING, COMMENT_BATCH,
                       COMMENT_FOOTER, COMMENT_HEADER, COMMENT_REVIEW,
                       COMMENT_STAFF_PICK, CONTRIBUTION_BATCH, LOGGING, MARGIN,
                       MODERATION_REWARD, SHEET, STEEM, TITLE_CURRENT,
                       TITLE_PREVIOUS, VP_COMMENTS, VP_TOTAL)
from contribution import Contribution


def comment_weights_table(comment_weights):
    """Prints a table containing the voting weight for comments made by
    moderators in each category.
    """
    table = PrettyTable()
    table.title = "COMMENT WEIGHTS"
    table.field_names = ["Category", "Weight"]

    for category, weight in comment_weights.items():
        table.add_row([category, f"{weight:.2f}%"])

    table.align["Category"] = "l"
    table.align["Weight"] = "r"

    print(table)


def get_comment_weights():
    """Returns a dictionary containing the key, value pair of the category and
    the voting weight needed upvote a review comment with each category's point
    equivalence in STU.
    """
    account = Account("utopian-io")

    comment_weights = {
        category: 100.0 * points / account.get_voting_value_SBD() for
        category, points in MODERATION_REWARD.items()
    }

    if LOGGING:
        comment_weights_table(comment_weights)

    return comment_weights


def update_weights(comment_weights, comment_usage):
    """Updates the weights used to upvote comments so that the actual voting
    power usage is equal to the estimated usage.
    """
    estimated_usage = 1.0 - VP_COMMENTS / 100.0
    actual_usage = 1.0 - comment_usage / 100.0
    scaler = np.log(estimated_usage) / np.log(actual_usage)

    for category in comment_weights.keys():
        comment_weights[category] *= scaler

    return comment_weights


def voting_power_usage_table(comment_vp, contribution_vp):
    """Prints a table containing the voting power usage of all comments and all
    contributions.
    """
    table = PrettyTable()
    table.title = "VOTING POWER USAGE"
    table.field_names = ["Type", "Usage"]

    table.add_row(["Comments", f"{comment_vp:.2f}%"])
    table.add_row(["Contributions", f"{contribution_vp:.2f}%"])
    table.add_row(["All", f"{comment_vp + contribution_vp:.2f}%"])

    table.align["Type"] = "l"
    table.align["Usage"] = "r"

    print(table)


def comment_voting_power(comments, comment_weights, scaling=1.0):
    """Returns the amount of voting power that will be used to upvote all the
    currently pending review comments.
    """
    voting_power = 100.0
    for contribution in comments:
        category = contribution["category"]
        try:
            voting_weight = comment_weights[category]
        except KeyError:
            voting_weight = comment_weights["task-request"]

        usage = scaling * voting_weight / 100.0 * 0.02 * voting_power
        voting_power -= usage

    return 100.0 - voting_power


def contribution_voting_power(contributions, voting_power, reward_scaler=None):
    """Returns the amount of voting power that will be used to upvote all the
    currently pending contributions.
    """
    starting_vp = voting_power
    scaler = 1.0
    for contribution in contributions:
        category = contribution["category"]
        voting_weight = contribution["voting_weight"]

        if reward_scaler:
            try:
                scaler = reward_scaler[category]
            except KeyError:
                scaler = reward_scaler["task-request"]

        usage = scaler * voting_weight / 100.0 * 0.02 * voting_power
        voting_power -= usage

    return starting_vp - voting_power


def category_share_table(category_share):
    """Prints a table containing each category and their share of the allocated
    voting power for contributions.
    """
    table = PrettyTable()
    table.title = "CATEGORY SHARE"
    table.field_names = ["Category", "Share"]

    total_share = sum(category_share.values())

    for category, share in category_share.items():
        table.add_row([category, f"{share:.2f}%"])

    table.add_row(["all", f"{total_share:.2f}%"])
    table.align["Category"] = "l"
    table.align["Share"] = "r"
    print(table)


def get_category_share(voting_power):
    """Returns a dictionary with a key, value pair of each category and their
    share of the calculated voting power that can be used for contributions.
    """
    total_vote = sum(CATEGORY_WEIGHTING.values())
    category_share = {category: max_vote / total_vote * voting_power
                      for category, max_vote in CATEGORY_WEIGHTING.items()}

    if LOGGING:
        category_share_table(category_share)

    return category_share


def category_usage_table(category_usage):
    """Prints a table containing each category and the amount of voting power
    will be used to upvote all contributions in the category.
    """
    table = PrettyTable()
    table.title = "CATEGORY USAGE"
    table.field_names = ["Category", "Usage"]

    for category, usage in category_usage.items():
        table.add_row([category, f"{usage:.2f}%"])

    table.add_row(["all", f"{sum(category_usage.values()):.2f}%"])

    table.align["Category"] = "l"
    table.align["Usage"] = "r"
    print(table)


def get_category_usage(contributions, voting_power):
    """Returns a dictionary containing the key, value pair of the category and
    the amount of voting power it will need to upvote all contributions in the
    category.
    """
    category_usage = {}
    for contribution in contributions:
        category = contribution["category"]

        if "task" in category:
            category = "task-request"

        category_usage.setdefault(category, 0)

        voting_weight = contribution["voting_weight"]
        vp_usage = voting_weight / 100.0 * 0.02 * voting_power

        category_usage[category] += vp_usage
        voting_power -= vp_usage

    if LOGGING:
        category_usage_table(category_usage)

    return category_usage


def new_share_table(new_share):
    """Prints a table containing the new share of the voting power of each
    category.
    """
    table = PrettyTable()
    table.title = "NEW CATEGORY USAGE"
    table.field_names = ["Category", "Usage"]

    for category, usage in new_share.items():
        table.add_row([category, f"{usage:.2f}%"])

    table.add_row(["all", f"{sum(new_share.values()):.2f}%"])

    table.align["Category"] = "l"
    table.align["Usage"] = "r"
    print(table)


def distribute_remainder(remainder, category_usage, new_share, need_more_vp):
    """Distributes the remaining voting power over the categories that need it.
    """
    while remainder > 0:
        # Get voting power needed for every category
        needed_per_category = {category: category_usage[category] - share
                               for category, share in new_share.items()
                               if category in need_more_vp}

        # Get category who needs the least to reach its usage
        least_under = min(needed_per_category.items(), key=itemgetter(1))
        least_under_category = least_under[0]
        least_needed = least_under[1]

        # If this amount can be added to all categories without using the
        # entire remainder then do this
        if len(needed_per_category) * least_needed < remainder:
            for category in need_more_vp:
                new_share[category] += least_needed
                remainder -= least_needed
            need_more_vp.remove(least_under_category)
        # Distribute the remainder evenly over the categories that need it
        else:
            remaining_categories = len(need_more_vp)
            for category in need_more_vp:
                percentage_share = 1.0 / remaining_categories
                to_be_added = percentage_share * remainder
                new_vp = new_share[category] + to_be_added

                # Category's new share is still less than what it needs
                if new_vp < category_usage[category]:
                    new_share[category] += to_be_added
                    remainder -= to_be_added
                # Category's new share is more than it needs, so distribute to
                # the other categories
                else:
                    not_needed = new_vp - category_usage[category]
                    remainder -= to_be_added - not_needed
                    new_share[category] = category_usage[category]

                remaining_categories -= 1

    if LOGGING:
        new_share_table(new_share)

    return new_share


def calculate_new_share(category_share, category_usage):
    """Calculates the new share of the voting power for each category."""
    new_share = {}
    remainder = 0
    need_more_vp = []

    for category, share in category_share.items():
        try:
            usage = category_usage[category]
            # Category's share is more than the voting power it will use
            if share > usage:
                remainder += share - usage
                new_share[category] = usage
            # Category needs more voting power to vote everything
            else:
                new_share[category] = share
                need_more_vp.append(category)
        except KeyError:
            remainder += share

    return distribute_remainder(remainder, category_usage, new_share,
                                need_more_vp)


def reward_scaler_table(category_scaling):
    """Prints a table containing each category and the scaler that the voting
    weight of contributions in each respective category will be multiplied
    with.
    """
    table = PrettyTable()
    table.title = "REWARD MULTIPLIER"
    table.field_names = ["Category", "Reward scaling"]

    for category, scaling in category_scaling.items():
        table.add_row([category, f"{scaling:.2f}"])

    table.align["Category"] = "l"
    table.align["Usage"] = "r"

    print(table)


def get_reward_scaler(category_usage, category_share):
    """Returns a dictionary containing the key, value pair of the category and
    the ratio that will be used to scale the voting_weight of contributions
    in the category.
    """
    category_ratio = {}

    for category, share in category_share.items():
        category_ratio[category] = share / category_usage[category]

    if LOGGING:
        reward_scaler_table(category_ratio)

    return category_ratio


def update_reward_scaler(reward_scaler, contribution_usage, comment_usage):
    """Updates the reward scaling dictionary so that the actual voting power
    usage is roughly the same as the estimated usage.
    """
    estimated_usage = 1.0 - (VP_TOTAL - comment_usage) / 100.0
    actual_usage = 1.0 - contribution_usage / 100.0
    scaler = np.log(estimated_usage) / np.log(actual_usage)

    for category in reward_scaler.keys():
        reward_scaler[category] *= scaler

    return reward_scaler


"""
VOTING PART
"""


def valid_translation(post):
    """Returns True if the translation contribution has the correct
    beneficiaries set, otherwise False.
    """
    beneficiaries = []
    for beneficiary in post.json()["beneficiaries"]:
        if beneficiary["account"] == "utopian.pay":
            weight = beneficiary["weight"]
            if weight >= 500:
                beneficiaries.append(True)

        if beneficiary["account"] == "davinci.pay":
            weight = beneficiary["weight"]
            if weight == 1000:
                beneficiaries.append(True)

    return all(beneficiaries)


def reply_to_contribution(contribution):
    """Replies to the contribution with a message confirming that it has been
    voted on.
    """
    post = Comment(contribution["url"])
    category = contribution["category"]

    if "task" in category:
        contribution_type = "task request"
    else:
        contribution_type = "contribution"

    body = COMMENT_HEADER.format(post.author)

    if contribution["staff_picked"]:
        body += COMMENT_STAFF_PICK.format(category)

    body += COMMENT_FOOTER.format(contribution_type)

    # post.reply(body, author=ACCOUNT)


def update_sheet(url, vote_successful=True, is_contribution=True):
    """Updates the status of a contribution or review comment in the
    spreadsheet to indicate whether it has been voted on (Yes) or if something
    has gone wrong (Error).
    """
    status = "Yes" if vote_successful else "Error"
    column_index = 11 if is_contribution else 10

    previous_reviewed = SHEET.worksheet(TITLE_PREVIOUS)
    current_reviewed = SHEET.worksheet(TITLE_CURRENT)

    if url in previous_reviewed.col_values(3):
        row_index = previous_reviewed.col_values(3).index(url) + 1
        previous_reviewed.update_cell(row_index, column_index, status)
    else:
        row_index = current_reviewed.col_values(3).index(url) + 1
        current_reviewed.update_cell(row_index, column_index, status)


def vote_on_contribution(contribution):
    """Tries to vote on the given contribution and updates the sheet with
    whether or not the vote was successful.
    """
    url = contribution["url"]
    category = contribution["category"]
    account = Account("sttest2")
    post = Comment(url, steem_instance=STEEM)

    voters = [vote["voter"] for vote in post.json()["active_votes"]]
    if ACCOUNT in voters:
        update_sheet(url, vote_successful=False)
        return

    allows_curation = post.json()["allow_curation_rewards"]
    if not allows_curation:
        update_sheet(url, vote_successful=False)
        return

    if category == "translations" and not valid_translation(post):
        update_sheet(url, vote_successful=False)
        return

    print(f"Voting on contribution {contribution['url']} with {contribution['voting_weight']:.2f}%")
    post.vote(contribution["voting_weight"], account=account)
    update_sheet(url)


def handle_contributions(contributions, multiplier):
    """Calculates the new weight of each contribution using the given
    multiplier and votes + comments on it.
    """
    for contribution in contributions:
        category = contribution["category"]
        weight_before = contribution["voting_weight"]

        try:
            weight_now = weight_before * multiplier[category]
        except KeyError:
            weight_now = weight_before * multiplier["task-request"]

        contribution["voting_weight"] = weight_now
        vote_on_contribution(contribution)
        reply_to_contribution(contribution)

        time.sleep(3)


def reply_to_comment(comment):
    """Replies to a review comment with a message confirming that it has been
    voted on.
    """
    repliers = [reply.author for reply in comment.get_replies()]

    if ACCOUNT not in repliers:
        pass
        # comment.reply(COMMENT_REVIEW.format(comment.author), author=ACCOUNT)


def vote_on_comment(comment, voting_weight):
    """Votes on the given comment if it hasn't already been voted on."""
    account = Account("sttest1")

    voters = [v.voter for v in comment.get_votes()]
    if ACCOUNT not in voters:
        try:
            print(f"Voting on comment {comment.permlink} with {voting_weight:.2f}%")
            comment.vote(voting_weight, account=account)
            return True
        except Exception:
            pass
    return False


def handle_comments(comments, comment_weights):
    """Uses the pre-calculated weights to upvote and reply to all pending
    review comments.
    """
    for comment in comments:
        category = comment["category"]
        contribution_url = comment["url"]
        moderator = comment["moderator"]
        comment_url = comment["comment_url"]
        url = f"{contribution_url}#@{moderator}/{comment_url}"

        beem_comment = Comment(url)

        voted_on = vote_on_comment(beem_comment, comment_weights[category])
        if voted_on:
            reply_to_comment(beem_comment)
        update_sheet(contribution_url, voted_on, is_contribution=False)

        time.sleep(3)


def main():
    comments = requests.get(COMMENT_BATCH).json()
    contributions = sorted(requests.get(CONTRIBUTION_BATCH).json(),
                           key=lambda x: x["voting_weight"], reverse=True)

    comment_weights = get_comment_weights()
    comment_usage = comment_voting_power(comments, comment_weights)

    if comment_usage > VP_COMMENTS:
        comment_weights = update_weights(comments, comment_weights)
        comment_usage = comment_voting_power(comments, comment_weights)

    voting_power = 100 - comment_usage


    contribution_usage = contribution_voting_power(contributions, voting_power)

    if contribution_usage + comment_usage > VP_TOTAL:
        contribution_usage = VP_TOTAL - comment_usage

    category_share = get_category_share(contribution_usage)
    category_usage = get_category_usage(contributions, voting_power)

    if contribution_usage + comment_usage == VP_TOTAL:
        new_share = calculate_new_share(category_share, category_usage)
    else:
        new_share = category_usage

    reward_scaler = get_reward_scaler(category_usage, new_share)

    contribution_usage = contribution_voting_power(contributions, voting_power,
                                                   reward_scaler)

    if contribution_usage > VP_TOTAL - comment_usage:
        reward_scaler = update_reward_scaler(reward_scaler, contribution_usage,
                                             comment_usage)

    print(contribution_voting_power(contributions, voting_power, reward_scaler))

    # handle_comments(comments, comment_weights)
    # handle_contributions(contributions, reward_scaler)


if __name__ == '__main__':
    main()
