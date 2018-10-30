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
from watson_developer_cloud.natural_language_understanding_v1 import (CategoriesResult,
                                                                      Features)

from constants import (ACCOUNT, CATEGORY_WEIGHTING, COMMENT_BATCH,
                       COMMENT_FOOTER, COMMENT_HEADER, COMMENT_REVIEW,
                       COMMENT_STAFF_PICK, CONTRIBUTION_BATCH, LOGGER, LOGGING,
                       MODERATION_REWARD, SHEET, STEEM, TESTING, TITLE_CURRENT,
                       TITLE_PREVIOUS, TRAIL_ACCOUNTS, VP_COMMENTS, VP_TOTAL,
                       WATSON_LABELS, WATSON_SCORE, WATSON_SERVICE)
from database.database_handler import DatabaseHandler

account = Account(ACCOUNT)


def comment_weights_table(comment_weights):
    """Prints a table containing the voting weight for comments made by
    moderators in each category.
    """
    table = PrettyTable()
    table.title = "COMMENT WEIGHTS"
    table.field_names = ["Category", "Weight"]

    for category, weight in sorted(comment_weights.items()):
        table.add_row([category, f"{weight:.2f}%"])

    table.align["Category"] = "l"
    table.align["Weight"] = "r"

    LOGGER.info(f"\n{table}")


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
    desired_usage = 1.0 - VP_COMMENTS / 100.0
    actual_usage = 1.0 - comment_usage / 100.0
    scaler = np.log(desired_usage) / np.log(actual_usage)

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

    LOGGER.info(f"\n{table}")


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

    for category, share in sorted(category_share.items()):
        table.add_row([category, f"{share:.2f}%"])

    table.add_row(["all", f"{total_share:.2f}%"])
    table.align["Category"] = "l"
    table.align["Share"] = "r"

    LOGGER.info(f"\n{table}")


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

    for category in sorted(CATEGORY_WEIGHTING.keys()):
        try:
            usage = category_usage[category]
        except KeyError:
            usage = 0
        table.add_row([category, f"{usage:.2f}%"])

    table.add_row(["all", f"{sum(category_usage.values()):.2f}%"])

    table.align["Category"] = "l"
    table.align["Usage"] = "r"

    LOGGER.info(f"\n{table}")


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
    table.title = "NEW CATEGORY SHARE"
    table.field_names = ["Category", "Share"]

    for category in sorted(CATEGORY_WEIGHTING.keys()):
        try:
            share = new_share[category]
        except KeyError:
            share = 0
        table.add_row([category, f"{share:.2f}%"])

    table.add_row(["all", f"{sum(new_share.values()):.2f}%"])

    table.align["Category"] = "l"
    table.align["Share"] = "r"

    LOGGER.info(f"\n{table}")


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

    LOGGER.info(f"\n{table}")


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
    desired_usage = 1.0 - (VP_TOTAL - comment_usage) / 100.0
    actual_usage = 1.0 - contribution_usage / 100.0
    scaler = np.log(desired_usage) / np.log(actual_usage)

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

    try:
        if not TESTING:
            post.reply(body, author=ACCOUNT)
            LOGGER.info(f"Replied to contribution: {contribution['url']}")
    except Exception as error:
        LOGGER.error("Something went wrong while trying to reply to the "
                     f"contribution: {contribution['url']}")


def update_sheet(url, vote_successful=True, is_contribution=True):
    """Updates the status of a contribution or review comment in the
    spreadsheet to indicate whether it has been voted on (Yes) or if something
    has gone wrong (Error).
    """
    status = "Yes" if vote_successful else "Error"
    column_index = 11 if is_contribution else 10

    previous_reviewed = SHEET.worksheet(TITLE_PREVIOUS)
    current_reviewed = SHEET.worksheet(TITLE_CURRENT)

    update_type = "contribution" if is_contribution else "comment"

    try:
        if url in previous_reviewed.col_values(3):
            row_index = previous_reviewed.col_values(3).index(url) + 1
            previous_reviewed.update_cell(row_index, column_index, status)
        else:
            row_index = current_reviewed.col_values(3).index(url) + 1
            current_reviewed.update_cell(row_index, column_index, status)
        LOGGER.info(f"Updated {update_type} in sheet: {url}")
    except Exception as error:
        LOGGER.error(f"Something went wrong while updating the {update_type}: "
                     f"{url} - {error}")


def vote_on_contribution(contribution):
    """Tries to vote on the given contribution and updates the sheet with
    whether or not the vote was successful.
    """
    url = contribution["url"]
    category = contribution["category"]
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

    try:
        voting_weight = contribution["voting_weight"]
        post.vote(voting_weight, account=account)
        LOGGER.info(f"Upvoted contribution ({voting_weight:.2f}%): "
                    f"{url}")
    except Exception as error:
        LOGGER.error("Something went wrong while upvoting the contribution: "
                     f"{url} - {error}")
        return
    return True


def handle_contributions(contributions, category_share, voting_power):
    """Votes and replies to the given contribution if there is still some mana
    left in its category's share.
    """
    for contribution in contributions:
        voting_weight = contribution["voting_weight"]
        category = contribution["category"]

        if "task" in category:
            category = "task-request"

        usage = voting_weight / 100.0 * 0.02 * voting_power

        if category_share[category] - usage < 0:
            continue

        voted_on = vote_on_contribution(contribution)
        if voted_on:
            reply_to_contribution(contribution)
            update_sheet(contribution["url"])

        category_share[category] -= usage
        voting_power -= usage

        time.sleep(3)

    LOGGER.info(f"Voting power after contributions: {voting_power:.2f}%")
    return voting_power


def reply_to_comment(comment):
    """Replies to a review comment with a message confirming that it has been
    voted on.
    """
    repliers = [reply.author for reply in comment.get_replies()]

    if ACCOUNT not in repliers:
        try:
            if not TESTING:
                comment.reply(COMMENT_REVIEW.format(comment.author),
                              author=ACCOUNT)
                LOGGER.info(f"Replied to comment: {comment.permlink}")
        except Exception as error:
            LOGGER.error("Something went wrong while replying to the comment: "
                         f"{comment.permlink} - {error}")
    else:
        LOGGER.error(f"Already replied to the comment: {comment.permlink}")


def vote_on_comment(comment, voting_weight):
    """Votes on the given comment if it hasn't already been voted on."""
    voters = [v.voter for v in comment.get_votes()]
    if ACCOUNT not in voters:
        try:
            comment.vote(voting_weight, account=account)
            LOGGER.info(f"Upvoted comment ({voting_weight:.2f}%): "
                        f"{comment.permlink}")
            return True
        except Exception as error:
            LOGGER.error("Something went wrong while upvoting the comment: "
                         f"{comment.permlink} - {error}")
            pass
    else:
        LOGGER.error(f"Already voted on the comment: {comment.permlink}")

    return False


def handle_comments(comments, comment_weights, voting_power):
    """Uses the pre-calculated weights to upvote and reply to all pending
    review comments.
    """
    for comment in comments:
        category = comment["category"]
        contribution_url = comment["url"]
        moderator = comment["moderator"]
        comment_url = comment["comment_url"]
        url = f"{moderator}/{comment_url}"

        beem_comment = Comment(url)
        voted_on = vote_on_comment(beem_comment, comment_weights[category])

        if voted_on:
            usage = comment_weights[category] / 100.0 * 0.02 * voting_power
            voting_power -= usage
            reply_to_comment(beem_comment)
            update_sheet(contribution_url, voted_on, is_contribution=False)

        time.sleep(3)

    LOGGER.info(f"Voting power after comments: {voting_power:.2f}%")
    return voting_power


def init_comments(comments):
    """Initialises everything needed for upvoting the comments."""
    comment_weights = get_comment_weights()
    comment_usage = comment_voting_power(comments, comment_weights)

    if comment_usage > VP_COMMENTS:
        comment_weights = update_weights(comment_weights, comment_usage)
        comment_usage = comment_voting_power(comments, comment_weights)

    LOGGER.info(f"Estimed voting power usage (comments): {comment_usage:.2f}%")
    return comment_weights, comment_usage


def init_contributions(contributions, comment_usage):
    """Initialises everything needed for upvoting the contributions."""
    voting_power = 100.0 - comment_usage
    contribution_usage = contribution_voting_power(contributions, voting_power)

    if contribution_usage + comment_usage > VP_TOTAL:
        contribution_usage = VP_TOTAL - comment_usage

    category_share = get_category_share(contribution_usage)
    category_usage = get_category_usage(contributions, voting_power)

    if contribution_usage + comment_usage == VP_TOTAL:
        new_share = calculate_new_share(category_share, category_usage)
    else:
        new_share = category_usage

    return new_share


def valid_trail_contribution(contribution):
    """Returns True if Watson's analysis determines it fits our labels, False
    otherwise.
    """
    response = WATSON_SERVICE.analyze(
        text=contribution.body,
        features=Features(categories=CategoriesResult())).get_result()

    for category in response["categories"]:
        label = category["label"]
        score = category["score"]
        if label in WATSON_LABELS and score >= WATSON_SCORE:
            return True

    return False


def trail_contributions(trail_name):
    """Returns all valid contributions that will be upvoted from the trail."""
    contributions = []
    database = DatabaseHandler.get_instance()
    trail_account = Account(trail_name)
    day_ago = datetime.now() - timedelta(days=1)
    week_ago = datetime.now() - timedelta(days=7)
    number_upvoted = database.number_upvoted(trail_name, week_ago)

    weight_trigger = TRAIL_ACCOUNTS[trail_name]["weight_trigger"]
    weight_multiplier = TRAIL_ACCOUNTS[trail_name]["weight_multiplier"]
    max_weight = TRAIL_ACCOUNTS[trail_name]["max_weight"] / 100.0
    self_vote_allowed = TRAIL_ACCOUNTS[trail_name]["self_vote_allowed"]
    check_context = TRAIL_ACCOUNTS[trail_name]["check_context"]
    upvote_limit = TRAIL_ACCOUNTS[trail_name]["upvote_limit"]
    is_priority = TRAIL_ACCOUNTS[trail_name]["is_priority"]

    for vote in trail_account.history_reverse(stop=day_ago, only_ops=["vote"]):
        if number_upvoted > upvote_limit:
            break

        weight = vote["weight"]
        author = vote["author"]
        voter = vote["voter"]

        if (weight < weight_trigger or voter != trail_name or
                (voter == author and not self_vote_allowed)):
            continue

        contribution = Comment(f"@{vote['author']}/{vote['permlink']}")
        voters = [v["voter"] for v in contribution.json()["active_votes"]]

        if ACCOUNT in voters:
            continue

        voting_weight = weight * weight_multiplier / 100.0

        if voting_weight > max_weight:
            voting_weight = max_weight

        if not check_context or valid_trail_contribution(contribution):
            contributions.append({
                "trail_name": trail_name,
                "author": author,
                "voting_weight": voting_weight,
                "contribution": contribution,
                "is_priority": is_priority,
            })
            number_upvoted += 1

    return contributions


def trail_multiplier(contributions, voting_power):
    """Returns a multiplier that will be used if the trail uses more than its
    allocated voting power.
    """
    priority_contributions = [contribution for contribution in contributions
                              if contribution["is_priority"]]

    # Calculate voting power share used by priority contributions
    for contribution in priority_contributions:
        voting_weight = contribution["voting_weight"]
        usage = voting_weight / 100.0 * 0.02 * voting_power
        voting_power -= usage

    max_usage = voting_power - 80.0

    if max_usage < 0:
        LOGGER.error("Not enough voting power left to upvote trail.")
        return 0.0

    total_usage = 0

    # Calculate voting power share used by the rest
    for contribution in contributions:
        voting_weight = contribution["voting_weight"]
        usage = voting_weight / 100.0 * 0.02 * voting_power

        total_usage += usage
        voting_power -= usage

    LOGGER.info(f"Estimed voting power usage (trail): {total_usage:.2f}%")

    if total_usage < max_usage:
        return 1.0

    # If non-priority contributions use too much voting power, scale weight
    desired_usage = 1.0 - max_usage / 100.0
    actual_usage = 1.0 - total_usage / 100.0
    multiplier = np.log(desired_usage) / np.log(actual_usage)

    LOGGER.info("Scaling non-priority trail contributions with multiplier: "
                f"{multiplier:.1f}%")

    return multiplier


def handle_trail(contributions, voting_power):
    """Upvotes and replies to all contributions in the trail."""
    database = DatabaseHandler.get_instance()

    contributions = sorted(
        contributions,
        key=lambda x: (x["is_priority"], x["voting_weight"]),
        reverse=True
    )

    for contribution in contributions:
        post = contribution["contribution"]
        trail_name = contribution["trail_name"]
        voting_weight = contribution["voting_weight"]
        usage = voting_weight / 100.0 * 0.02 * voting_power

        if voting_power - usage < 80.0:
            LOGGER.error("Voting power reached 80% while voting on the trail.")
            break

        try:
            comment = TRAIL_ACCOUNTS[trail_name]["comment"].format(
                trail_name,
                contribution["author"])
        except Exception:
            comment = TRAIL_ACCOUNTS[trail_name]["comment"]

        try:
            voting_power -= usage
            post.vote(voting_weight, account=account)
            if not TESTING:
                post.reply(comment, author=ACCOUNT)
                LOGGER.info("Voted and replied to trail contribution: "
                            f"{post.permlink}")
        except Exception as error:
            LOGGER.error("Something went wrong while voting and replying to "
                         f"the trail contribution: {post.permlink}")
            continue

        if not database.contribution_exists(post.authorperm):
            database.add_contribution(post.id, trail_name, post.authorperm,
                                      datetime.now())

        time.sleep(3)

    LOGGER.info(f"Voting power after trail: {voting_power:.2f}%")


def init_trail():
    """Initialises everything needed for upvoting the trail's contributions."""
    contributions = []

    for trail_name in TRAIL_ACCOUNTS.keys():
        contributions.extend(trail_contributions(trail_name))
    contributions = sorted(contributions, key=lambda x: x["voting_weight"])

    return contributions


def main():
    voting_power = account.get_voting_power()

    if voting_power < 100.0:
        return

    LOGGER.info("STARTED BATCH VOTE")
    comments = requests.get(COMMENT_BATCH).json()
    comment_weights, comment_usage = init_comments(comments)

    contributions = sorted(requests.get(CONTRIBUTION_BATCH).json(),
                           key=lambda x: x["score"], reverse=True)
    category_share = init_contributions(contributions, comment_usage)

    voting_power = handle_comments(comments, comment_weights, voting_power)
    voting_power = handle_contributions(contributions, category_share,
                                        voting_power)

    trail_contributions = init_trail()
    handle_trail(trail_contributions, voting_power)
    LOGGER.info("FINISHED BATCH VOTE")

if __name__ == '__main__':
    main()
