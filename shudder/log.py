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

"""Configuration for shudder"""
import logging
import sys

class LoggerWriter:
    def __init__(self, level):
        # self.level is really like using log.debug(message)
        # at least in my case
        self.level = level

    def write(self, message):
        # if statement reduces the amount of newlines that are
        # printed to the logger
        if message != '\n':
            self.level(message)

    def flush(self):
        # create a flush method so things can be flushed when
        # the system wants to. Not sure if simply 'printing'
        # sys.stderr is the correct way to do it, but it seemed
        # to work properly for me.
        self.level(sys.stderr)

def init_logging():
    LOG_FILENAME = '/var/log/shudder/shudder.log'
    logging.basicConfig(filename=LOG_FILENAME,
                        level=logging.INFO,
                        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                        datefmt='%a, %d %b %Y %H:%M:%S',
                        )
    logger = logging.getLogger()
    sys.stdout = LoggerWriter(logger.info)
    sys.stderr = LoggerWriter(logger.error)
