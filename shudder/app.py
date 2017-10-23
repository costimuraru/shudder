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

"""Start polling of SQS and metadata."""

import logging
import time
import requests
import signal
import socket
import subprocess
import sys
import shudder.queue as queue
import shudder.metadata as metadata
from shudder.config import CONFIG


def receive_signal(signum, stack):
    if signum in [1,2,3,15]:
        logging.info('Caught signal %s, exiting.' % str(signum))
        sys.exit()
    else:
        logging.debug('Caught signal %s, ignoring.' % str(signum))

last_heart_beat = 0
def send_heart_beat(message):
    global last_heart_beat
    time_now = time.time()
    if time_now - last_heart_beat >= 60:
        logging.info('Sending a heart beat to AWS.')
        queue.record_lifecycle_action_heartbeat(message)
        last_heart_beat = time.time()


def replace_macros(command):
    hostname = socket.gethostname()
    command = command.replace("INSTANCEID_MACRO", queue.INSTANCE_ID)
    command = command.replace("REGION_MACRO", queue.REGION)
    command = command.replace("HOSTNAME_MACRO", hostname)
    return command


def start_shudder():
    logging.info('Started shudder.')

    uncatchable = ['SIG_DFL','SIGSTOP','SIGKILL']
    for i in [x for x in dir(signal) if x.startswith("SIG")]:
        if not i in uncatchable:
            signum = getattr(signal,i)
            signal.signal(signum,receive_signal)

    sqs_connection, sqs_queue = queue.create_queue()
    sns_connection, subscription_arn = queue.subscribe_sns(sqs_queue)
    while True:
        message = queue.poll_queue(sqs_connection, sqs_queue)
        if message or metadata.poll_instance_metadata():
            queue.clean_up_sns(sns_connection, subscription_arn, sqs_queue)
            if 'endpoint' in CONFIG:
                requests.get(CONFIG["endpoint"])
            if 'endpoints' in CONFIG:
                for endpoint in CONFIG["endpoints"]:
                    logging.info('Calling endpoint %s' % endpoint)
                    requests.get(endpoint)
            if 'commands' in CONFIG:
                for command in CONFIG["commands"]:
                    command = replace_macros(command)
                    logging.info('Running command: %s' % command)
                    process = subprocess.Popen(command.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    while process.poll() is None:
                        time.sleep(1)
                        send_heart_beat(message)

                    out, err = process.communicate()
                    if out:
                        logging.info('Command output\n>>>>\n%s\n<<<<' % out)
                    if err:
                        logging.error('Command error\n>>>>\n%s\n<<<<' % err)
            logging.info('Sending a COMPLETE lifecycle action.')
            queue.complete_lifecycle_action(message)
            logging.info('Finished successfully. Exiting now.')
            sys.exit(0)
        logging.info('Waiting for TERMINATION trigger.')
        time.sleep(10)
