#! /usr/bin/env python3
# coding = utf-8

import boto3
import json
import requests
import os
import base64
import random

def get_user(event):
    user = event.get('user')
    if not user:
        user = 'Unknown user'
    else:
        user = user.get('login')
    return user

def text_from_message(message):
    comment = message.get('comment')
    if comment:
        user = get_user(comment)
        text = comment.get('body')
        return '{} commented:\n```{}```'.format(user, text)
    issue = message.get('issue')
    if issue:
        user = get_user(issue)
        title = issue.get('title')
        return '{} {} issue "{}"'.format(user, message.get('action'), title)

def send_to_slack(message, config=None):
    # Inject failure for demo purposes — simulate that sending to Slack failed
    # for some reason, e.g.
    # In real life this probability is much less but still not zero, at all!
    if random.randint(0, 1) == 0:
        raise RuntimeError("Imitated Slack failure")

    if config is None:
        config = json.load(open('/function/code/config', 'r'))
    text = text_from_message(message)
    if not text:
        text = 'Unhandled message: ' + json.dumps(message)

    body = {'text': text}
    url = config['slack_webhook']
    resp = requests.post(url, data={'payload':json.dumps(body)})
    assert(resp.text == 'ok')

def ymq_handler(event, context):
    config = json.load(open('/function/code/config', 'r'))
    for message in event['messages']:
        try:
            body = json.loads(message['details']['message']['body'])
        except:
            print("Bad message: " + json.dumps(message))
            continue

        send_to_slack(message=body, config=config)

def make_ymq_client():
    config = json.load(open('/function/code/config', 'r'))
    session = boto3.session.Session()
    return session.client(
        service_name='sqs',
        aws_access_key_id=config['access_key_id'],
        aws_secret_access_key=config['secret_access_key'],
        endpoint_url='https://message-queue.api.cloud.yandex.net',
        region_name='ru-central1'
    )

def send_to_ymq_queue(queue_url, data):
    client = make_ymq_client()
    client.send_message(
        QueueUrl=queue_url,
        MessageBody=data
    )

def called_from_ymq_trigger(event, context):
    if event.get('messages'):
        return True
    else:
        return False

def make_response():
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/plain'
        },
        'isBase64Encoded': False,
        'body': 'Request processed',
    }
