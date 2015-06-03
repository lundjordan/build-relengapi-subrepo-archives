# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import logging
import os
import requests
import urllib2

from boto.s3.key import Key


from flask import current_app
from relengapi.blueprints.subrepo_archives.util import retry
from relengapi.lib import celery

log = logging.getLogger(__name__)

ARCHIVES = os.path.join(os.getcwd(), 'archives')
HGMO_URL_TEMPLATE = "http://hg.mozilla.org/{branch}/archive/{rev}.tar.gz/testing/mozharness"
GET_EXPIRES_IN = 300

# @retry(urllib2.URLError)
def download_archive(url, rev):
    if not os.path.exists(ARCHIVES):
        os.mkdir(ARCHIVES)

    dest = os.path.join(ARCHIVES, "{}.tar.gz".format(rev))
    src = urllib2.urlopen(url)
    data = src.read()
    with open(dest, "wb") as code:
        code.write(data)
    return dest


def upload_file_to_s3(key, value, region, bucket):
    s3 = current_app.aws.connect_to('s3', region)
    k = Key(s3.get_bucket(bucket))
    k.key = key
    k.set_contents_from_filename(value)

    return s3.generate_url(expires_in=GET_EXPIRES_IN, method='GET', bucket=bucket, key=key)


@celery.task(bind=True)
def create_and_upload_archive(self, branch, rev):
    return_status = "Task complete! See usw2_s3_url and use1_s3_url results for archive locations."
    print branch, rev
    log.info(branch + ' ' + rev)
    hgmo_url = HGMO_URL_TEMPLATE.format(branch=branch, rev=rev)
    usw2_s3_url = ''
    use1_s3_url = ''

    self.update_state(state='PROGRESS',
                      meta={'status': 'ensuring hg.mozilla.org subdir archive exists',
                            'hgmo_url': hgmo_url})
    # ensure rev really exists on hg.m.o/BRANCH/REV
    r = requests.head(hgmo_url)
    if r.status_code == 200:
        self.update_state(state='PROGRESS',
                          meta={'status': 'downloading hg.mozilla.org subdir archive.',
                                'hgmo_url': hgmo_url})
        # download mh archive from hg.m.o based on rev/branch
        archive = download_archive(hgmo_url, rev)
        if archive and type(archive) == str and os.path.exists(archive):
            self.update_state(state='PROGRESS',
                              meta={'status': 'uploading archive to s3 buckets',
                                    'hgmo_url': hgmo_url})
            usw2_s3_url = upload_file_to_s3('{}-{}'.format(branch, rev), archive, 'us-west-2',
                                            'subrepo-archives-basic-us-west-2')
            use1_s3_url = upload_file_to_s3('{}-{}'.format(branch, rev), archive, 'us-east-1',
                                            'subrepo-archives-basic-us-east-1')
        else:
            return_status = "Could not download hg.m.o archive. Check exception logs for details."
            log.warning(return_status)
    else:
        return_status = "Can't find hg.m.o archive given branch and rev. Does url {} exist? Request " \
                      "Response code: {}".format(hgmo_url, r.status_code)
        log.warning(return_status)

    return {
        'status': return_status,
        'hgmo_url': hgmo_url,
        'usw2_s3_url': usw2_s3_url,
        'use1_s3_url': use1_s3_url,
    }

