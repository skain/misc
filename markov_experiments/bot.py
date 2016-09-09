"""
From: http://hirelofty.com/blog/how-build-slack-bot-mimics-your-colleague/
"""
import json
import markovify
import re
import time

from slackclient import SlackClient


BOT_TOKEN = "bot user API token"
GROUP_TOKEN = "xoxp-2595967997-12774219255-78167785238-bbe03dfae2"

MESSAGE_QUERY = "from:username_to_parrot"
MESSAGE_PAGE_SIZE = 100
DEBUG = True


def _load_db():
    """
    Reads 'database' from a JSON file on disk.
    Returns a dictionary keyed by unique message permalinks.
    """

    try:
        with open('message_db.json', 'r') as json_file:
            messages = json.loads(json_file.read())
    except IOError:
        with open('message_db.json', 'w') as json_file:
            json_file.write('{}')
        messages = {}

    return messages


def _store_db(obj):
    """
    Takes a dictionary keyed by unique message permalinks and writes it to the JSON 'database' on
    disk.
    """

    with open('message_db.json', 'w') as json_file:
        json_file.write(json.dumps(obj))

    return True


def _query_messages(client, page=1):
    """
    Convenience method for querying messages from Slack API.
    """
    if DEBUG:
        print("requesting page {}".format(page))

    return client.api_call('search.messages', query=MESSAGE_QUERY, count=MESSAGE_PAGE_SIZE,
                           page=page)


def _add_messages(message_db, new_messages):
    """
    Search through an API response and add all messages to the 'database' dictionary.
    Returns updated dictionary.
    """
    for match in new_messages['messages']['matches']:
        message_db[match['permalink']] = match['text']

    return message_db


# get all messages, build a giant text corpus
def build_text_model():
    """
    Read the latest 'database' off disk and build a new markov chain generator model.
    Returns TextModel.
    """
    if DEBUG:
        print("Building new model...")

    messages = _load_db()
    return markovify.Text(" ".join(messages.values()), state_size=2)


def format_message(original):
    """
    Do any formatting necessary to markon chains before relaying to Slack.
    """
    if original is None:
        return

    # Clear <> from urls
    cleaned_message = re.sub(r'<(htt.*)>', '\1', original)

    return cleaned_message


def fetch_new_messages():
    # Messages will get queried by a different auth token
    # So we'll temporarily instantiate a new client with that token
    group_sc = SlackClient(GROUP_TOKEN)

    messages_db = {}

    # Get first page of messages
    new_messages = _query_messages(group_sc)
    total_pages = new_messages['messages']['paging']['pages']

    # store new messages
    messages_db = _add_messages(messages_db, new_messages)

    # If any subsequent pages are present, get those too
    if total_pages > 1:
        for page in range(2, total_pages + 1):
            new_messages = _query_messages(group_sc, page=page)
            messages_db = _add_messages(messages_db, new_messages)

    return messages_db

    # Make sure we close any sockets to the other group.
    del group_sc


def update_corpus(sc, channel):
    """
    Queries for new messages and adds them to the 'database' object if new ones are found.
    Reports back to the channel where the update was requested on status.
    """

    if sc:
        sc.rtm_send_message(channel, "Leveling up...")

    # Load the current database
    messages_db = _load_db()
    new_messages = fetch_new_messages()
    if len(new_messages) > 0:
        _add_messages(messages_db, new_messages)

    starting_count = len(messages_db.keys())

    # See if any new keys were added
    final_count = len(messages_db.keys())
    new_message_count = final_count - starting_count

    # If the count went up, save the new 'database' to disk, report the stats.
    if final_count > starting_count:
        # Write to disk since there is new data.
        _store_db(messages_db)
        if sc:
            sc.rtm_send_message(channel,
                                "I have been imbued with the power of {} new messages!".format(
                                    new_message_count
                                ))
    else:
        if sc:
            sc.rtm_send_message(channel, "No new messages found :(")

    if DEBUG:
        print("Start: {}".format(starting_count), "Final: {}".format(final_count),
              "New: {}".format(new_message_count))

    return new_message_count


def run_slackbot(model):
    # Create the slackclient instance
    sc = SlackClient(BOT_TOKEN)

    # Connect to slack
    if not sc.rtm_connect():
        raise Exception("Couldn't connect to slack.")

    # Where the magic happens

    while True:
        # Examine latest events
        for slack_event in sc.rtm_read():

            # Disregard events that are not messages
            if not slack_event.get('type') == "message":
                continue

            message = slack_event.get("text")
            user = slack_event.get("user")
            channel = slack_event.get("channel")

            if not message or not user:
                continue

            ######
            # Commands we're listening for.
            ######

            if "parrot me" in message.lower():
                markov_chain = model.make_sentence()
                sc.rtm_send_message(channel, format_message(markov_chain))

            if "level up parrot" in message.lower():
                # Fetch new messages.  If new ones are found, rebuild the text model
                if update_corpus(sc, channel) > 0:
                    model = build_text_model()

        # Sleep for half a second
        time.sleep(0.5)


def main():
    """
    Startup logic and the main application loop to monitor Slack events.
    """

    # build the text model
    # model = build_text_model()
    # run_slackbot(model)

    update_corpus(None, 'dev-team')


if __name__ == '__main__':
    main()
