# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import wsme.types


class MozharnessArchiveTask(wsme.types.Base):
    """Represents a running task and its current state
    """

    #: this is the current state of the task
    #: e.g. "PENDING", "PROGRESS", "SUCCESS", "FAILURE"
    state = unicode

    #: current msg status of task
    #: e.g. "Downloading archive from hg.m.o"
    status = unicode

    #: subdir artifact url from hg.m.o based on rev
    hgmo_url = unicode

    #: us-west-2 s3 url for mozharness archive
    usw2_s3_url = unicode

    #: us-east-1 s3 url for mozharness archive
    use1_s3_url = unicode


