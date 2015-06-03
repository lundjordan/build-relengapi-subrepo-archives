# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from flask import Blueprint, url_for, jsonify
from relengapi.lib import api
from flask import redirect
from flask import current_app
from relengapi.blueprints.types import MozharnessArchiveTask
from relengapi.blueprints.tasks import create_and_upload_archive
import logging

bp = Blueprint('subrepo_archives', __name__)
log = logging.getLogger(__name__)

GET_EXPIRES_IN = 300

@bp.route('/status/<task_id>')
@api.apimethod(MozharnessArchiveTask, unicode)
def task_status(task_id):
    task = create_and_upload_archive.AsyncResult(task_id)
    task_info = task.info or {}
    response = {
        'state': task.state,
        'hgmo_url': task_info.get('hgmo_url', ''),
        'usw2_s3_url': task_info.get('usw2_s3_url', ''),
        'use1_s3_url': task_info.get('use1_s3_url', ''),
    }
    if task.state != 'FAILURE':
        response['status'] = task_info.get('status', 'no status available at this point.')
    else:
        # something went wrong
        response['status'] = str(task.info)  # this is the exception raised

    return MozharnessArchiveTask(**response)


@bp.route('/<branch>/<rev>')
@api.apimethod(None, unicode, unicode, status_code=302)
def get_archive(branch, rev, region='us-west-2'):
    s3 = current_app.aws.connect_to('s3', region)
    bucket = s3.get_bucket('subrepo-archives-{}'.format(region))
    key = '{branch}-{rev}'.format(branch=branch, rev=rev)

    # first, see if the key exists
    if not bucket.get_key(key):
        # create and upload archive to s3
        # since this is a long'ish request, let's acknowledge and complete it
        # asynchronously in a separate task
        task = create_and_upload_archive.apply_async(args=[branch, rev], task_id=rev)
        return {}, 202, {'Location': url_for('subrepo_archives.task_status', task_id=task.id)}

    log.info("generating GET URL to {}, expires in {}s".format(rev, GET_EXPIRES_IN))
    # return 302 pointing to s3 url with archive
    signed_url = s3.generate_url(
        method='GET', expires_in=GET_EXPIRES_IN,
        bucket='subrepo-archives-{}'.format(region), key=key
    )
    return redirect(signed_url)

