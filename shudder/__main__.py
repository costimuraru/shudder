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

import daemon
import daemon.pidfile

if __name__ == "__main__":
    context = daemon.DaemonContext(
        umask=0o002,
        pidfile=daemon.pidfile.PIDLockFile('/var/run/shudder/shudder.pid')
    )

    with context:
        from log import init_logging
        init_logging()
        
        from app import start_shudder
        start_shudder()
