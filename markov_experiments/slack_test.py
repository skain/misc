import pdb
import json
import markovify
import re
import time

from slackclient import SlackClient


BOT_TOKEN = "bot user API token"
GROUP_TOKEN = "xoxp-2595967997-12774219255-78167785238-bbe03dfae2"
MESSAGE_QUERY = "from:skain"
MESSAGE_PAGE_SIZE = 100


def _query_messages(client, page=1):
    """
    Convenience method for querying messages from Slack API.
    """
    return client.api_call('search.messages', query=MESSAGE_QUERY, count=MESSAGE_PAGE_SIZE,
                           page=page)


def _add_messages(message_db, new_messages):
    """
    Search through an API response and add all messages to the 'database' dictionary.
    Returns updated dictionary.
    """
    if 'messages' not in new_messages:
        print('no messages found in _add_messages')
        pdb.set_trace()
    try:
        for match in new_messages['messages']['matches']:
            message_db[match['permalink']] = match['text']

        return message_db
    except:
        print('error adding messages')
        pdb.set_trace()


def fetch_new_messages():
    # Messages will get queried by a different auth token
    # So we'll temporarily instantiate a new client with that token
    group_sc = SlackClient(GROUP_TOKEN)

    messages_db = {}

    # Get first page of messages
    new_messages = _query_messages(group_sc)
    if 'messages' not in new_messages:
        print('no messages found after query_messages')
        pdb.set_trace()
    total_pages = new_messages['messages']['paging']['pages']

    # store new messages
    if 'messages' not in new_messages:
        print('no messages found after total_pages calc')
        pdb.set_trace()
    messages_db = _add_messages(messages_db, new_messages)

    # If any subsequent pages are present, get those too
    if total_pages > 1:
        for page in range(2, total_pages + 1):
            new_messages = _query_messages(group_sc, page=page)
            messages_db = _add_messages(messages_db, new_messages)

    return messages_db

    # Make sure we close any sockets to the other group.
    del group_sc


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


def update_corpus():
    """
    Queries for new messages and adds them to the 'database' object if new ones are found.
    """

    # Load the current database
    messages_db = _load_db()
    starting_count = len(messages_db.keys())
    new_messages = fetch_new_messages()

    if len(new_messages) > 0:
        messages_db.update(new_messages)

    # See if any new keys were added
    final_count = len(messages_db.keys())
    new_message_count = final_count - starting_count

    # If the count went up, save the new 'database' to disk, report the stats.
    if final_count > starting_count:
        # Write to disk since there is new data.
        _store_db(messages_db)

    return new_message_count


if __name__ == '__main__':
    update_corpus()
