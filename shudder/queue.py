# Copyright 2014 Scopely, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Module for setting up an sqs queue subscribed to
an sns topic polling for messages pertaining to our
impending doom.

"""
import logging
import json
import boto3
import hashlib

from shudder.config import CONFIG
import shudder.metadata as metadata

INSTANCE_ID = metadata.get_instance_id()
REGION = metadata.get_region()
QUEUE_NAME = "{prefix}-{id}".format(prefix=CONFIG['sqs_prefix'], id=INSTANCE_ID)
SNS_TOPIC = CONFIG['sns_topic'].replace("REGION_MACRO", REGION).replace(" ", "")

def create_queue():
    """Creates the SQS queue and returns the queue url and metadata"""
    logging.info("Creating queue %s" % QUEUE_NAME)
    conn = boto3.client('sqs', region_name=REGION)
    queue_metadata = conn.create_queue(QueueName=QUEUE_NAME, Attributes={'VisibilityTimeout':'3600'})
    return queue_metadata['QueueUrl']

def get_queue(queue_url):
    sqs = boto3.resource('sqs', region_name=REGION)
    queue = sqs.Queue(queue_url)
    return queue

def subscribe_sns(queue_url):
    """Attach a policy to allow incoming connections from SNS"""
    logging.info("Subscribe SNS to the queue %s" % str(queue_url))
    queue = get_queue(queue_url)
    statement_id = hashlib.md5((SNS_TOPIC +  queue.attributes.get('QueueArn')).encode('utf-8')).hexdigest()
    statement_id_exists = False
    existing_policy = queue.attributes.get('Policy')
    if existing_policy:
        policy = json.loads(existing_policy)
    else:
        policy = {}
    if 'Version' not in policy:
        policy['Version'] = '2008-10-17'
    if 'Statement' not in policy:
        policy['Statement'] = []
    # See if a Statement with the Sid exists already.
    for statement in policy['Statement']:
        if statement['Sid'] == statement_id:
           statement_id_exists = True
    if not statement_id_exists:
        statement = {'Action': 'SQS:SendMessage',
            'Effect': 'Allow',
            'Principal': {'AWS': '*'},
            'Resource': queue.attributes.get('QueueArn'),
            'Sid': statement_id,
            'Condition': {"ForAllValues:ArnEquals":{"aws:SourceArn":SNS_TOPIC}}}
        policy['Statement'].append(statement)
    queue.set_attributes(Attributes={'Policy':json.dumps(policy)})
    """Subscribes the SNS topic to the queue."""
    conn = boto3.client('sns', region_name=REGION)
    sub = conn.subscribe(TopicArn=SNS_TOPIC, Protocol='sqs', Endpoint=queue.attributes.get('QueueArn'))
    sns_arn = sub['SubscriptionArn']
    return conn, sns_arn


def getJsonMessage(msg):
    try:
        first_box = json.loads(msg.body)
        return json.loads(first_box['Message'])
    except Exception as e:
        logging.error("Unexpected error while parsing SQS message '%s': %s" % (str(msg.body), str(e)))
        return None


def should_terminate(json_message):
    """Check if the termination message is about our instance"""
    if json_message is None:
        return False

    termination_msg = 'autoscaling:EC2_INSTANCE_TERMINATING'
    if 'LifecycleTransition' in json_message and json_message['LifecycleTransition'] == termination_msg and INSTANCE_ID == json_message['EC2InstanceId']:
        return True
    else:
        return False


def clean_up_sns(sns_conn, sns_arn, queue_url):
    """Clean up SNS subscription and SQS queue"""
    logging.info("Cleaning up SNS and SQS")
    queue = get_queue(queue_url)
    queue.delete()
    sns_conn.unsubscribe(SubscriptionArn=sns_arn)


def record_lifecycle_action_heartbeat(message):
    """Let AWS know we're still in the process of shutting down"""
    conn = boto3.client('autoscaling', region_name=REGION)
    conn.record_lifecycle_action_heartbeat(
        LifecycleHookName=message['LifecycleHookName'],
        AutoScalingGroupName=message['AutoScalingGroupName'],
        LifecycleActionToken=message['LifecycleActionToken'],
        InstanceId=message['EC2InstanceId'])


def complete_lifecycle_action(message):
    """Let AWS know it's safe to terminate the instance now"""
    conn = boto3.client('autoscaling', region_name=REGION)
    conn.complete_lifecycle_action(
        LifecycleHookName=message['LifecycleHookName'],
        AutoScalingGroupName=message['AutoScalingGroupName'],
        LifecycleActionToken=message['LifecycleActionToken'],
        LifecycleActionResult='CONTINUE',
        InstanceId=message['EC2InstanceId'])


def poll_queue(queue_url):
    """Poll SQS until we get a termination message."""
    queue = get_queue(queue_url)
    messages = queue.receive_messages()
    termination_message = None
    for message in messages:
        json_message = getJsonMessage(message)
        if should_terminate(json_message):
            logging.info("Received termination message for this instance: %s" % str(json_message))
            termination_message = json_message
        else:
            logging.info("Ignoring termination message: %s - %s" % (message, json_message))
        message.delete()

    return termination_message
