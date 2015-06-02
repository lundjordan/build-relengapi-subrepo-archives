# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import time
from random import randint
from functools import wraps
import logging

logger = logging.getLogger(__name__)

def retry(exception, tries=3, delay=2, backoff=2, jitter=True):
    def decorator_retry(f):
        @wraps
        def f_retry(*args, **kwargs):
            # re-assign so that decorator vars are mutable
            mtries, mdelay, mbackoff = tries, delay, backoff
            while tries > 0:
                try:
                    return f(*args, **kwargs)
                except exception, e:
                    logger.exception("{}, Retrying in {} seconds...".format(str(e), mdelay))
                    mtries -= 1
                    if jitter:
                        mdelay += randint(1, 3)
                    time.sleep(mdelay)
                    mdelay *= backoff
            return f(*args, **kwargs)
        return f_retry
    return decorator_retry

