# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import logging
import os
import tempfile
import requests
import urllib2

from boto.s3.key import Key


from flask import current_app
from relengapi.lib import celery

log = logging.getLogger(__name__)

ARCHIVES = os.path.join(os.getcwd(), 'archives')
HGMO_URL_TEMPLATE = "http://hg.mozilla.org/{branch}/archive/{rev}.tar.gz/testing/mozharness"
GET_EXPIRES_IN = 300


def upload_url_to_s3(key, url, region, bucket, suffix):
    s3 = current_app.aws.connect_to('s3', region)
    k = Key(s3.get_bucket(bucket))
    k.key = key

    temp_file = tempfile.NamedTemporaryFile(mode="wb", suffix=".{}".format(suffix), delete=False)
    data = urllib2.urlopen(url).read()
    with open(temp_file.name, "wb") as tmpf:
        tmpf.write(data)
    k.set_contents_from_filename(temp_file.name)
    os.unlink(temp_file.name)  # clean up tmp file

    return s3.generate_url(expires_in=GET_EXPIRES_IN, method='GET', bucket=bucket, key=key)


@celery.task(bind=True)
def create_and_upload_archive(self, rev, repo, suffix):
    return_status = "Task complete!"
    cfg = current_app.config['SUBREPO_MOZHARNESS_CFG']
    s3_urls = {}
    hgmo_url = cfg['HGMO_TEMPLATE'].format(repo=repo, rev=rev, suffix=suffix)

    self.update_state(state='PROGRESS',
                      meta={'status': 'ensuring hg.mozilla.org subdir archive exists',
                            'hgmo_url': hgmo_url})
    # ensure hg repo url really exists
    resp = requests.get(hgmo_url)
    if resp.status_code == 200:
        self.update_state(state='PROGRESS',
                          meta={'status': 'uploading archive to s3 buckets', 'hgmo_url': hgmo_url})
        key = '{repo}-{rev}.{suffix}'.format(repo=os.path.basename(repo), rev=rev, suffix=suffix)
        for bucket in cfg['S3_BUCKETS']:
            s3_urls[bucket['REGION']] = upload_url_to_s3(key, hgmo_url, bucket['REGION'],
                                                         bucket['NAME'], suffix)
        if not any(s3_urls.values()):
            return_status = "Could not upload any archives to s3. Check logs for errors."
            log.warning(return_status)
    else:
        return_status = "Can't find hg.m.o archive given branch and rev. Does url {} exist? Request " \
                        "Response code: {}".format(hgmo_url, resp.status_code)
        log.warning(return_status)

    return {
        'status': return_status,
        'hgmo_url': hgmo_url,
        's3_urls': s3_urls,
    }
