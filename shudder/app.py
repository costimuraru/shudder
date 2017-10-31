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


def run_command(message, command):
    try:
        command = replace_macros(command)
        logging.info('Running command: %s' % command)
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        while process.poll() is None:
            time.sleep(1)
            send_heart_beat(message)

        out, err = process.communicate()
        if out.strip():
            logging.info('Command output\n>>>>\n%s\n<<<<' % out)
        if err.strip():
            logging.error('Command error\n>>>>\n%s\n<<<<' % err)
        logging.info("Successfully ran command.")
    except Exception as e:
        logging.error("Unexpected error while running command '%s': %s" % (str(command), str(e)))


def call_endpoint(endpoint):
    try:
        logging.info('Calling endpoint %s' % endpoint)
        requests.get(endpoint)
    except Exception as e:
        logging.error("Unexpected error while calling endpoint '%s': %s" % (str(endpoint), str(e)))


def start_shudder():
    logging.info('Started shudder.')

    uncatchable = ['SIG_DFL','SIGSTOP','SIGKILL']
    for i in [x for x in dir(signal) if x.startswith("SIG")]:
        if not i in uncatchable:
            signum = getattr(signal,i)
            signal.signal(signum,receive_signal)

    queue_url = queue.create_queue()
    sns_connection, subscription_arn = queue.subscribe_sns(queue_url)
    while True:
        message = queue.poll_queue(queue_url)
        if message or metadata.poll_instance_metadata():
            queue.clean_up_sns(sns_connection, subscription_arn, queue_url)
            if 'endpoint' in CONFIG:
                call_endpoint(CONFIG["endpoint"])
            if 'endpoints' in CONFIG:
                for endpoint in CONFIG["endpoints"]:
                    call_endpoint(endpoint)
            if 'commands' in CONFIG:
                for command in CONFIG["commands"]:
                    run_command(message, command)
            logging.info('Sending a COMPLETE lifecycle action.')
            queue.complete_lifecycle_action(message)
            logging.info('Finished successfully. Exiting now.')
            sys.exit(0)
        logging.info('Waiting for TERMINATION trigger.')
        time.sleep(10)
