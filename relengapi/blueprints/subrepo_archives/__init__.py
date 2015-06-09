# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import os

from flask import Blueprint
from flask import current_app
from flask import redirect
from flask import url_for
from relengapi.blueprints.subrepo_archives.tasks import create_and_upload_archive
from relengapi.blueprints.subrepo_archives.types import MozharnessArchiveTask
from relengapi.lib import api
from werkzeug.exceptions import NotFound

bp = Blueprint('subrepo_archives', __name__)
log = logging.getLogger(__name__)

GET_EXPIRES_IN = 300

@bp.route('/')
@api.apimethod({unicode: unicode})
def hello():
    return {'message': 'hello world'}


@bp.route('/status/<task_id>')
@api.apimethod(MozharnessArchiveTask, unicode)
def task_status(task_id):
    task = create_and_upload_archive.AsyncResult(task_id)
    task_info = task.info or {}
    response = {
        'state': task.state,
        'hgmo_url': task_info.get('hgmo_url', ''),
        's3_urls': task_info.get('s3_urls', {})
    }
    if task.state != 'FAILURE':
        response['status'] = task_info.get('status', 'no status available at this point.')
    else:
        # something went wrong
        response['status'] = str(task.info)  # this is the exception raised

    return MozharnessArchiveTask(**response)


@bp.route('/mozharness/<rev>')
@api.apimethod(None, unicode, unicode, unicode, unicode, status_code=302)
def get_archive(rev, repo="mozilla-central", region='us-west-2', suffix='tar.gz'):
    cfg = current_app.config['SUBREPO_MOZHARNESS_CFG']

    bucket_region = None
    bucket_name = None
    for bucket in cfg['S3_BUCKETS']:
        if region in bucket['REGION']:
            bucket_region = bucket['REGION']
            bucket_name = bucket['NAME']

    # sanity check
    if not bucket_name or not bucket_region:
        valid_regions = str([bucket['REGION'] for bucket in cfg['S3_BUCKETS']])
        log.warning('Unsupported region given: "{}" Valid Regions "{}"'.format(region, valid_regions))
        raise NotFound

    s3 = current_app.aws.connect_to('s3', bucket_region)
    bucket = s3.get_bucket(bucket_name)
    key = '{repo}-{rev}'.format(repo=os.path.basename(repo), rev=rev)

    # first, see if the key exists
    if not bucket.get_key(key):
        # now check to see if we already have a task started for this request
        task_id = 'mozharness-{}'.format(rev)
        if create_and_upload_archive.AsyncResult(task_id).state != 'PROGRESS':
            create_and_upload_archive.apply_async(args=[rev, repo, suffix], task_id=task_id)
        return {}, 202, {'Location': url_for('subrepo_archives.task_status', task_id=task_id)}

    log.info("generating GET URL to {}, expires in {}s".format(rev, GET_EXPIRES_IN))
    # return 302 pointing to s3 url with archive
    signed_url = s3.generate_url(
        method='GET', expires_in=GET_EXPIRES_IN,
        bucket='subrepo-archives-{}'.format(region), key=key
    )
    return redirect(signed_url)

