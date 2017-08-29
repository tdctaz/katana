# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

import datetime
import sqlalchemy as sa
from twisted.trial import unittest
from twisted.internet import task, defer
from buildbot.db import buildrequests, builds
from buildbot.db.buildrequests import Queue
from buildbot.test.util import connector_component, db
from buildbot.test.fake import fakedb
from buildbot.util import UTC, epoch2datetime
from buildbot.status.results import RESUME, CANCELED, BEGINNING

class TestBuildsetsConnectorComponent(
            connector_component.ConnectorComponentMixin,
            unittest.TestCase):

    # test that the datetime translations are done correctly by specifying
    # the epoch timestamp and datetime objects explicitly.  These should
    # pass regardless of the local timezone used while running tests!
    CLAIMED_AT = datetime.datetime(1978, 6, 15, 12, 31, 15, tzinfo=UTC)
    CLAIMED_AT_EPOCH = 266761875
    SUBMITTED_AT = datetime.datetime(1979, 6, 15, 12, 31, 15, tzinfo=UTC)
    SUBMITTED_AT_EPOCH = 298297875
    COMPLETE_AT = datetime.datetime(1980, 6, 15, 12, 31, 15, tzinfo=UTC)
    COMPLETE_AT_EPOCH = 329920275
    BSID = 567
    BSID2 = 5670
    MASTER_ID = "set in setUp"
    OTHER_MASTER_ID = "set in setUp"

    MASTER_NAME = "testmaster"
    MASTER_INCARN = "pid123-boot456789"

    def setUp(self):
        self.MASTER_ID = fakedb.FakeBuildRequestsComponent.MASTER_ID
        self.OTHER_MASTER_ID = self.MASTER_ID + 1111
        d = self.setUpConnectorComponent(
            table_names=[ 'patches', 'changes', 'sourcestamp_changes',
                'buildsets', 'buildset_properties', 'buildrequests',
                'objects', 'buildrequest_claims', 'sourcestamps', 'sourcestampsets', 'builds' ])

        def finish_setup(_):
            self.db.buildrequests = \
                    buildrequests.BuildRequestsConnectorComponent(self.db)
            self.db.builds = builds.BuildsConnectorComponent(self.db)
            self.db.master.getObjectId = lambda : defer.succeed(self.MASTER_ID)
        d.addCallback(finish_setup)

        # set up a sourcestamp and buildset for use below
        d.addCallback(lambda _ :
            self.insertTestData([
                fakedb.SourceStampSet(id=234),
                fakedb.SourceStamp(id=234, sourcestampsetid=234),
                fakedb.Object(id=self.MASTER_ID, name="fake master",
                                         class_name="BuildMaster"),
                fakedb.Object(id=self.OTHER_MASTER_ID, name="other master",
                                         class_name="BuildMaster"),
                fakedb.Buildset(id=self.BSID, sourcestampsetid=234),
            ]))

        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    # tests

    def test_getBuildRequest(self):
        # ned fakedb.BuildRequestClaim
        d = self.insertTestData([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID, buildername="bbb",
                complete=1, results=75, priority=7,
                submitted_at=self.SUBMITTED_AT_EPOCH,
                complete_at=self.COMPLETE_AT_EPOCH),
            fakedb.BuildRequestClaim(
                brid=44, objectid=self.MASTER_ID,
                claimed_at=self.CLAIMED_AT_EPOCH),
        ])
        d.addCallback(lambda _ :
                self.db.buildrequests.getBuildRequest(44))
        def check(brdict):
            self.assertEqual(brdict,
                    dict(slavepool=None, artifactbrid=None, brid=44, buildsetid=self.BSID, buildername="bbb",
                        priority=7, claimed=True, mergebrid=None, mine=True, complete=True,
                        results=75, startbrid=None, claimed_at=self.CLAIMED_AT,
                        submitted_at=self.SUBMITTED_AT, triggeredbybrid = None,
                        complete_at=self.COMPLETE_AT))
        d.addCallback(check)
        return d

    def test_getBuildRequest_missing(self):
        d = self.db.buildrequests.getBuildRequest(44)
        def check(brdict):
            self.assertEqual(brdict, None)
        d.addCallback(check)
        return d

    def do_test_getBuildRequests_claim_args(self, **kwargs):
        expected = kwargs.pop('expected')
        d = self.insertTestData([
            # 50: claimed by this master
            fakedb.BuildRequest(id=50, buildsetid=self.BSID),
            fakedb.BuildRequestClaim(brid=50, objectid=self.MASTER_ID,
                    claimed_at=self.CLAIMED_AT_EPOCH),

            # 51: claimed by another master
            fakedb.BuildRequest(id=51, buildsetid=self.BSID),
            fakedb.BuildRequestClaim(brid=51, objectid=self.OTHER_MASTER_ID,
                    claimed_at=self.CLAIMED_AT_EPOCH),

            # 52: unclaimed
            fakedb.BuildRequest(id=52, buildsetid=self.BSID),

            # 53: unclaimed but complete (should not appear for claimed=False)
            fakedb.BuildRequest(id=53, buildsetid=self.BSID, complete=1),
        ])
        d.addCallback(lambda _ :
                self.db.buildrequests.getBuildRequests(**kwargs))
        def check(brlist):
            self.assertEqual(sorted([ br['brid'] for br in brlist ]),
                             sorted(expected))
        d.addCallback(check)
        return d

    def test_getBuildRequests_no_claimed_arg(self):
        return self.do_test_getBuildRequests_claim_args(
                expected=[50, 51, 52, 53])

    def test_getBuildRequests_claimed_mine(self):
        return self.do_test_getBuildRequests_claim_args(
                claimed="mine",
                expected=[50])

    def test_getBuildRequests_claimed_true(self):
        return self.do_test_getBuildRequests_claim_args(
                claimed=True,
                expected=[50, 51])

    def test_getBuildRequests_unclaimed(self):
        return self.do_test_getBuildRequests_claim_args(
                claimed=False,
                expected=[52])

    def do_test_getBuildRequests_buildername_arg(self, **kwargs):
        expected = kwargs.pop('expected')
        d = self.insertTestData([
            # 8: 'bb'
            fakedb.BuildRequest(id=8, buildsetid=self.BSID, buildername='bb'),
            # 9: 'cc'
            fakedb.BuildRequest(id=9, buildsetid=self.BSID, buildername='cc'),
            # 10: 'cc'
            fakedb.BuildRequest(id=10, buildsetid=self.BSID, buildername='cc'),
        ])
        d.addCallback(lambda _ :
                self.db.buildrequests.getBuildRequests(**kwargs))
        def check(brlist):
            self.assertEqual(sorted([ br['brid'] for br in brlist ]),
                             sorted(expected))
        d.addCallback(check)
        return d

    def test_getBuildRequests_buildername_single(self):
        return self.do_test_getBuildRequests_buildername_arg(
                buildername='bb',
                expected=[8])

    def test_getBuildRequests_buildername_multiple(self):
        return self.do_test_getBuildRequests_buildername_arg(
                buildername='cc',
                expected=[9,10])

    def test_getBuildRequests_buildername_none(self):
        return self.do_test_getBuildRequests_buildername_arg(
                buildername='dd',
                expected=[])

    def do_test_getBuildRequests_complete_arg(self, **kwargs):
        expected = kwargs.pop('expected')
        d = self.insertTestData([
            # 70: incomplete
            fakedb.BuildRequest(id=70, buildsetid=self.BSID,
                complete=0, complete_at=None),
            # 80: complete
            fakedb.BuildRequest(id=80, buildsetid=self.BSID,
                complete=1,
                complete_at=self.COMPLETE_AT_EPOCH),
            # 81: complete but no complete_at
            fakedb.BuildRequest(id=81, buildsetid=self.BSID,
                complete=1, complete_at=0),
            # 82: complete_at set but complete is false, so not complete
            fakedb.BuildRequest(id=82, buildsetid=self.BSID,
                complete=0,
                complete_at=self.COMPLETE_AT_EPOCH),
        ])
        d.addCallback(lambda _ :
                self.db.buildrequests.getBuildRequests(**kwargs))
        def check(brlist):
            self.assertEqual(sorted([ br['brid'] for br in brlist ]),
                             sorted(expected))
        d.addCallback(check)
        return d

    def test_getBuildRequests_complete_none(self):
        return self.do_test_getBuildRequests_complete_arg(
                expected=[ 70, 80, 81, 82])

    def test_getBuildRequests_complete_true(self):
        return self.do_test_getBuildRequests_complete_arg(
                complete=True,
                expected=[ 80, 81 ])

    def test_getBuildRequests_complete_false(self):
        return self.do_test_getBuildRequests_complete_arg(
                complete=False,
                expected=[ 70, 82 ])

    def test_getBuildRequests_bsid_arg(self):
        d = self.insertTestData([
            # the buildset that we are *not* looking for
            fakedb.Buildset(id=self.BSID+1, sourcestampsetid=234),

            fakedb.BuildRequest(id=70, buildsetid=self.BSID,
                complete=0, complete_at=None),
            fakedb.BuildRequest(id=71, buildsetid=self.BSID+1,
                complete=0, complete_at=None),
            fakedb.BuildRequest(id=72, buildsetid=self.BSID,
                complete=0, complete_at=None),
        ])
        d.addCallback(lambda _ :
                self.db.buildrequests.getBuildRequests(bsid=self.BSID))
        def check(brlist):
            self.assertEqual(sorted([ br['brid'] for br in brlist ]),
                             sorted([70, 72]))
        d.addCallback(check)
        return d

    def test_getBuildRequests_combo(self):
        d = self.insertTestData([
            # 44: everything we want
            fakedb.BuildRequest(id=44, buildsetid=self.BSID, buildername="bbb",
                complete=1, results=92,
                complete_at=self.COMPLETE_AT_EPOCH),
            fakedb.BuildRequestClaim(brid=44, objectid=self.MASTER_ID,
                    claimed_at=self.CLAIMED_AT_EPOCH),

            # 45: different buildername
            fakedb.BuildRequest(id=45, buildsetid=self.BSID, buildername="ccc",
                complete=1,
                complete_at=self.COMPLETE_AT_EPOCH),
            fakedb.BuildRequestClaim(brid=45, objectid=self.MASTER_ID,
                    claimed_at=self.CLAIMED_AT_EPOCH),

            # 46: incomplete
            fakedb.BuildRequest(id=46, buildsetid=self.BSID, buildername="bbb",
                complete=0, results=92,
                complete_at=0),
            fakedb.BuildRequestClaim(brid=46, objectid=self.MASTER_ID,
                    claimed_at=self.CLAIMED_AT_EPOCH),

            # 47: unclaimed
            fakedb.BuildRequest(id=47, buildsetid=self.BSID, buildername="bbb",
                complete=1, results=92,
                complete_at=self.COMPLETE_AT_EPOCH),

            # 48: claimed by other
            fakedb.BuildRequest(id=48, buildsetid=self.BSID, buildername="bbb",
                complete=1, results=92,
                complete_at=self.COMPLETE_AT_EPOCH),
            fakedb.BuildRequestClaim(brid=48, objectid=self.OTHER_MASTER_ID,
                    claimed_at=self.CLAIMED_AT_EPOCH),

            # 49: different bsid
            fakedb.Buildset(id=self.BSID+1, sourcestampsetid=234),
            fakedb.BuildRequest(id=49, buildsetid=self.BSID+1,
                buildername="bbb", complete=1, results=92,
                complete_at=self.COMPLETE_AT_EPOCH),
            fakedb.BuildRequestClaim(brid=49, objectid=self.MASTER_ID,
                    claimed_at=self.CLAIMED_AT_EPOCH),
        ])
        d.addCallback(lambda _ :
                self.db.buildrequests.getBuildRequests(buildername="bbb",
                    claimed="mine", complete=True, bsid=self.BSID))
        def check(brlist):
            self.assertEqual([ br['brid'] for br in brlist ], [ 44 ])
        d.addCallback(check)
        return d

    def do_test_getBuildRequests_branch_arg(self, **kwargs):
        expected = kwargs.pop('expected')
        d = self.insertTestData([
            fakedb.BuildRequest(id=70, buildsetid=self.BSID+1),
            fakedb.Buildset(id=self.BSID+1, sourcestampsetid=self.BSID+1),
            fakedb.SourceStampSet(id=self.BSID+1),
            fakedb.SourceStamp(sourcestampsetid=self.BSID+1,
                               branch='branch_A'),

            fakedb.BuildRequest(id=80, buildsetid=self.BSID+2),
            fakedb.Buildset(id=self.BSID+2, sourcestampsetid=self.BSID+2),
            fakedb.SourceStampSet(id=self.BSID+2),
            fakedb.SourceStamp(sourcestampsetid=self.BSID+2,
                               repository='repository_A'),

            fakedb.BuildRequest(id=90, buildsetid=self.BSID+3),
            fakedb.Buildset(id=self.BSID+3, sourcestampsetid=self.BSID+3),
            fakedb.SourceStampSet(id=self.BSID+3),
            fakedb.SourceStamp(sourcestampsetid=self.BSID+3,
                               branch='branch_A', repository='repository_A'),
        ])
        d.addCallback(lambda _ :
                self.db.buildrequests.getBuildRequests(**kwargs))
        def check(brlist):
            self.assertEqual(sorted([ br['brid'] for br in brlist ]),
                             sorted(expected))
        d.addCallback(check)
        return d

    def test_getBuildRequests_branch(self):
      return self.do_test_getBuildRequests_branch_arg(branch='branch_A',
                                                      expected=[70, 90])

    def test_getBuildRequests_branch_empty(self):
      return self.do_test_getBuildRequests_branch_arg(branch='absent_branch',
                                                      expected=[])

    def test_getBuildRequests_repository(self):
      return self.do_test_getBuildRequests_branch_arg(
          repository='repository_A', expected=[80, 90])

    def test_getBuildRequests_repository_empty(self):
      return self.do_test_getBuildRequests_branch_arg(
          repository='absent_repository', expected=[])

    def test_getBuildRequests_repository_and_branch(self):
      return self.do_test_getBuildRequests_branch_arg(
          repository='repository_A', branch='branch_A', expected=[90])

    def test_getBuildRequests_no_repository_nor_branch(self):
      return self.do_test_getBuildRequests_branch_arg(expected=[70, 80, 90])

    def do_test_claimBuildRequests(self, rows, now, brids, expected=None,
                                  expfailure=None, claimed_at=None):
        clock = task.Clock()
        clock.advance(now)

        d = self.insertTestData(rows)
        d.addCallback(lambda _ :
            self.db.buildrequests.claimBuildRequests(brids=brids,
                        claimed_at=claimed_at, _reactor=clock))
        def check(brlist):
            self.assertNotEqual(expected, None,
                    "unexpected success from claimBuildRequests")
            def thd(conn):
                reqs_tbl = self.db.model.buildrequests
                claims_tbl = self.db.model.buildrequest_claims
                q = sa.select([ reqs_tbl.outerjoin(claims_tbl,
                                        reqs_tbl.c.id == claims_tbl.c.brid) ])
                results = conn.execute(q).fetchall()
                self.assertEqual(
                    sorted([ (r.id, r.claimed_at, r.objectid)
                             for r in results ]),
                    sorted(expected))
            return self.db.pool.do(thd)
        d.addCallback(check)
        def fail(f):
            if not expfailure:
                raise f
            f.trap(expfailure)
        d.addErrback(fail)
        return d

    def test_claimBuildRequests_single(self):
        return self.do_test_claimBuildRequests([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID),
            ], 1300305712, [ 44 ],
            [ (44, 1300305712, self.MASTER_ID) ])

    def test_claimBuildRequests_single_explicit_claimed_at(self):
        return self.do_test_claimBuildRequests([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID),
            ], 1300305712, [ 44 ],
            [ (44, 14000000, self.MASTER_ID) ],
            claimed_at=epoch2datetime(14000000))

    def test_claimBuildRequests_multiple(self):
        return self.do_test_claimBuildRequests([
                fakedb.BuildRequest(id=44, buildsetid=self.BSID),
                fakedb.BuildRequest(id=45, buildsetid=self.BSID),
                fakedb.BuildRequest(id=46, buildsetid=self.BSID),
            ], 1300305712, [ 44, 46 ],
            [
                (44, 1300305712, self.MASTER_ID),
                (45, None, None),
                (46, 1300305712, self.MASTER_ID),
            ])

    def test_claimBuildRequests_stress(self):
        return self.do_test_claimBuildRequests([
                fakedb.BuildRequest(id=id, buildsetid=self.BSID)
                for id in xrange(1, 1000)
            ], 1300305713, range(1, 1000),
            [
                (id, 1300305713, self.MASTER_ID)
                for id in xrange(1, 1000)
            ])

    def test_claimBuildRequests_other_master_claim(self):
        return self.do_test_claimBuildRequests([
                fakedb.BuildRequest(id=44, buildsetid=self.BSID),
                fakedb.BuildRequestClaim(brid=44,
                    objectid=self.OTHER_MASTER_ID,
                    claimed_at=1300103810),
            ], 1300305712, [ 44 ],
            expfailure=buildrequests.AlreadyClaimedError)

    @db.skip_for_dialect('mysql')
    def test_claimBuildRequests_other_master_claim_stress(self):
        d = self.do_test_claimBuildRequests(
            [ fakedb.BuildRequest(id=id, buildsetid=self.BSID)
              for id in range(1, 1000) ] +
            [
                fakedb.BuildRequest(id=1000, buildsetid=self.BSID),
                # the fly in the ointment..
                fakedb.BuildRequestClaim(brid=1000,
                    objectid=self.OTHER_MASTER_ID, claimed_at=1300103810),
            ], 1300305712, range(1, 1001),
            expfailure=buildrequests.AlreadyClaimedError)
        def check(_):
            # check that [1,1000) were not claimed, and 1000 is still claimed
            def thd(conn):
                tbl = self.db.model.buildrequest_claims
                q = tbl.select()
                results = conn.execute(q).fetchall()
                self.assertEqual([ (r.brid, r.objectid, r.claimed_at)
                    for r in results ][:10],
                        [ (1000, self.OTHER_MASTER_ID, 1300103810) ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_claimBuildRequests_sequential(self):
        now = 120350934
        clock = task.Clock()
        clock.advance(now)

        d = self.insertTestData([
                fakedb.BuildRequest(id=44, buildsetid=self.BSID),
                fakedb.BuildRequest(id=45, buildsetid=self.BSID),
        ])
        d.addCallback(lambda _ :
            self.db.buildrequests.claimBuildRequests(brids=[44],
                        _reactor=clock))
        d.addCallback(lambda _ :
            self.db.buildrequests.claimBuildRequests(brids=[45],
                        _reactor=clock))
        def check(brlist):
            def thd(conn):
                reqs_tbl = self.db.model.buildrequests
                claims_tbl = self.db.model.buildrequest_claims
                join = reqs_tbl.outerjoin(claims_tbl,
                        reqs_tbl.c.id == claims_tbl.c.brid)
                q = join.select(claims_tbl.c.claimed_at == None)
                results = conn.execute(q).fetchall()
                self.assertEqual(results, [])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def do_test_reclaimBuildRequests(self, rows, now, brids, expected=None,
                                  expfailure=None):
        clock = task.Clock()
        clock.advance(now)

        d = self.insertTestData(rows)
        d.addCallback(lambda _ :
            self.db.buildrequests.reclaimBuildRequests(brids=brids,
                        _reactor=clock))
        def check(brlist):
            self.assertNotEqual(expected, None,
                    "unexpected success from claimBuildRequests")
            def thd(conn):
                reqs_tbl = self.db.model.buildrequests
                claims_tbl = self.db.model.buildrequest_claims
                q = sa.select([ reqs_tbl.outerjoin(claims_tbl,
                                        reqs_tbl.c.id == claims_tbl.c.brid) ])
                results = conn.execute(q).fetchall()
                self.assertEqual(
                    sorted([ (r.id, r.claimed_at, r.objectid)
                             for r in results ]),
                    sorted(expected))
            return self.db.pool.do(thd)
        d.addCallback(check)
        def fail(f):
            if not expfailure:
                raise f
            f.trap(expfailure)
        d.addErrback(fail)
        return d

    def test_reclaimBuildRequests(self):
        return self.do_test_reclaimBuildRequests([
                fakedb.BuildRequest(id=44, buildsetid=self.BSID),
                fakedb.BuildRequestClaim(brid=44, objectid=self.MASTER_ID,
                    claimed_at=1300103810),
            ], 1300305712, [ 44 ],
            # note that the time is updated
            [ (44, 1300305712, self.MASTER_ID) ])

    def test_reclaimBuildRequests_fail(self):
        d = self.do_test_reclaimBuildRequests([
                fakedb.BuildRequest(id=44, buildsetid=self.BSID),
                fakedb.BuildRequestClaim(brid=44, objectid=self.MASTER_ID,
                    claimed_at=1300103810),
                fakedb.BuildRequest(id=45, buildsetid=self.BSID),
                fakedb.BuildRequestClaim(brid=45, objectid=self.OTHER_MASTER_ID,
                    claimed_at=1300103810),
            ], 1300305712, [ 44, 45 ],
            expfailure=buildrequests.AlreadyClaimedError)
        def check(_):
            # check that the time wasn't updated on 44, noting that MySQL does
            # not support this.
            if self.db_engine.dialect.name == 'mysql':
                return
            def thd(conn):
                tbl = self.db.model.buildrequest_claims
                q = tbl.select(order_by=tbl.c.brid)
                results = conn.execute(q).fetchall()
                self.assertEqual([ (r.brid, r.claimed_at, r.objectid)
                                    for r in results ], [
                        (44, 1300103810, self.MASTER_ID),
                        (45, 1300103810, self.OTHER_MASTER_ID),
                    ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def do_test_completeBuildRequests(self, rows, now, expected=None,
                                     expfailure=None, brids=[44],
                                     complete_at=None):
        clock = task.Clock()
        clock.advance(now)

        d = self.insertTestData(rows)
        d.addCallback(lambda _ :
            self.db.buildrequests.completeBuildRequests(brids=brids,
                                            results=7, complete_at=complete_at,
                                            _reactor=clock))
        def check(brlist):
            self.assertNotEqual(expected, None,
                    "unexpected success from completeBuildRequests")
            def thd(conn):
                tbl = self.db.model.buildrequests
                q = sa.select([ tbl.c.id, tbl.c.complete,
                                 tbl.c.results, tbl.c.complete_at ])
                results = conn.execute(q).fetchall()
                self.assertEqual(sorted(map(tuple, results)), sorted(expected))
            return self.db.pool.do(thd)
        d.addCallback(check)
        def fail(f):
            if not expfailure:
                raise f
            f.trap(expfailure)
        d.addErrback(fail)
        return d

    def test_completeBuildRequests(self):
        return self.do_test_completeBuildRequests([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID),
            fakedb.BuildRequestClaim(brid=44, objectid=self.MASTER_ID,
                    claimed_at=1300103810),
            ], 1300305712,
            [ (44, 1, 7, 1300305712) ])

    def test_completeBuildRequests_explicit_time(self):
        return self.do_test_completeBuildRequests([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID),
            fakedb.BuildRequestClaim(brid=44, objectid=self.MASTER_ID,
                    claimed_at=1300103810),
            ], 1300305712,
            [ (44, 1, 7, 999999) ],
            complete_at=epoch2datetime(999999))

    def test_completeBuildRequests_multiple(self):
        return self.do_test_completeBuildRequests([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID),
            fakedb.BuildRequestClaim(brid=44, objectid=self.MASTER_ID,
                    claimed_at=1300103810),
            fakedb.BuildRequest(id=45, buildsetid=self.BSID),
            fakedb.BuildRequestClaim(brid=45, objectid=self.OTHER_MASTER_ID,
                    claimed_at=1300103811),
            fakedb.BuildRequest(id=46, buildsetid=self.BSID),
            fakedb.BuildRequestClaim(brid=46, objectid=self.MASTER_ID,
                    claimed_at=1300103812),
            ], 1300305712,
            [ (44, 1, 7, 1300305712),
              (45, 0, -1, 0),
              (46, 1, 7, 1300305712),
            ], brids=[44, 46])

    def test_completeBuildRequests_stress(self):
        return self.do_test_completeBuildRequests([
                fakedb.BuildRequest(id=id, buildsetid=self.BSID)
                for id in range(1, 280)
            ] + [
                fakedb.BuildRequestClaim(brid=id, objectid=self.MASTER_ID,
                        claimed_at=1300103810)
                for id in range(1, 280)
            ], 1300305712,
            [ (id, 1, 7, 1300305712)
                for id in range(1, 280)
            ], brids=range(1, 280))

    def test_completeBuildRequests_multiple_notmine(self):
        # note that the requests are completed even though they are not mine!
        return self.do_test_completeBuildRequests([
            # two unclaimed requests
            fakedb.BuildRequest(id=44, buildsetid=self.BSID),
            fakedb.BuildRequest(id=45, buildsetid=self.BSID),
            # and one claimed by another master
            fakedb.BuildRequest(id=46, buildsetid=self.BSID),
            fakedb.BuildRequestClaim(brid=46, objectid=self.OTHER_MASTER_ID,
                    claimed_at=1300103812),
            ], 1300305712,
            [ (44, 1, 7, 1300305712),
              (45, 1, 7, 1300305712),
              (46, 1, 7, 1300305712), ],
            brids=[44, 45, 46])

    def test_completeBuildRequests_already_completed(self):
        return self.do_test_completeBuildRequests([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID,
                complete=1, complete_at=1300104190),
            ], 1300305712,
            expfailure=buildrequests.NotClaimedError)

    def test_completeBuildRequests_no_such(self):
        return self.do_test_completeBuildRequests([
            fakedb.BuildRequest(id=45, buildsetid=self.BSID),
            ], 1300305712,
            expfailure=buildrequests.NotClaimedError)

    def do_test_unclaimMethod(self, method, expected):
        d = self.insertTestData([
            # 44: a complete build (should not be unclaimed)
            fakedb.BuildRequest(id=44, buildsetid=self.BSID,
                complete=1, results=92,
                complete_at=self.COMPLETE_AT_EPOCH),
            fakedb.BuildRequestClaim(brid=44, objectid=self.MASTER_ID,
                claimed_at=self.CLAIMED_AT_EPOCH),

            # 45: incomplete build belonging to this incarnation
            fakedb.BuildRequest(id=45, buildsetid=self.BSID,
                complete=0, complete_at=0),
            fakedb.BuildRequestClaim(brid=45, objectid=self.MASTER_ID,
                claimed_at=self.CLAIMED_AT_EPOCH),

            # 46: incomplete build belonging to another master
            fakedb.BuildRequest(id=46, buildsetid=self.BSID,
                complete=0, complete_at=0),
            fakedb.BuildRequestClaim(brid=46, objectid=self.OTHER_MASTER_ID,
                claimed_at=self.CLAIMED_AT_EPOCH),

            # 47: unclaimed
            fakedb.BuildRequest(id=47, buildsetid=self.BSID,
                complete=0, complete_at=0),

            # 48: claimed by this master, but recently
            fakedb.BuildRequest(id=48, buildsetid=self.BSID,
                complete=0, complete_at=0),
            fakedb.BuildRequestClaim(brid=48, objectid=self.MASTER_ID,
                claimed_at=self.CLAIMED_AT_EPOCH-50),

            # 49: incomplete old build belonging to another master
            fakedb.BuildRequest(id=49, buildsetid=self.BSID,
                complete=0, complete_at=0),
            fakedb.BuildRequestClaim(brid=49, objectid=self.OTHER_MASTER_ID,
                claimed_at=self.CLAIMED_AT_EPOCH - 1000),
        ])
        d.addCallback(lambda _ : method())
        def check(brlist):
            def thd(conn):
                # just select the unclaimed requests
                reqs_tbl = self.db.model.buildrequests
                claims_tbl = self.db.model.buildrequest_claims
                join = reqs_tbl.outerjoin(claims_tbl,
                        reqs_tbl.c.id == claims_tbl.c.brid)
                q = sa.select([ reqs_tbl.c.id ],
                        from_obj=[ join ],
                        whereclause=claims_tbl.c.claimed_at == None)
                results = conn.execute(q).fetchall()
                self.assertEqual(sorted([ r.id for r in results ]),
                                 sorted(expected))
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_unclaimExpiredRequests(self):
        clock = task.Clock()
        clock.advance(self.CLAIMED_AT_EPOCH)

        meth = self.db.buildrequests.unclaimExpiredRequests
        return self.do_test_unclaimMethod(
            lambda : meth(100, _reactor=clock),
            [47, 49])

    def test_unclaimBuildRequests(self):
        to_unclaim = [
            44, # completed -> unclaimed anyway
            45, # incomplete -> unclaimed
            46, # from another master -> not unclaimed
            47, # unclaimed -> still unclaimed
            48, # claimed -> unclaimed
            49, # another master -> not unclaimed
            50  # no such buildrequest -> no error
        ]
        return self.do_test_unclaimMethod(
            lambda : self.db.buildrequests.unclaimBuildRequests(to_unclaim),
            [44, 45, 47, 48])

    def buildRequestWithSources(self, complete=1, results=0):
        return self.insertTestData([
            fakedb.BuildRequest(id=1, buildsetid=1, buildername="builder",
                                complete=complete, results=results,
                                submitted_at=self.SUBMITTED_AT_EPOCH,
                                complete_at=self.COMPLETE_AT_EPOCH),
            fakedb.Buildset(id=1, sourcestampsetid=1),
            fakedb.SourceStampSet(id=1),
            fakedb.SourceStamp(id=1, revision='a', codebase='1',
                               sourcestampsetid=1, branch='master', repository='z'),
            fakedb.SourceStamp(id=2, revision='b', codebase='2', sourcestampsetid=1,
                               branch='staging', repository='w')])

    def test_downloadArtifact(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="A", complete=1, results=0),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="B", complete=1, results=0,
                                     submitted_at=self.SUBMITTED_AT_EPOCH, complete_at=self.COMPLETE_AT_EPOCH,
                                     triggeredbybrid=1, startbrid=1)
                 ]
        d = self.insertTestData(breqs)
        d.addCallback(lambda _ :
                self.db.buildrequests.getBuildRequestTriggered(triggeredbybrid=1, buildername='B'))

        def check(brdict):
            self.assertEqual(brdict,
                    dict(artifactbrid=None, brid=2, buildername="B", buildsetid=2,
                        complete=True, complete_at=self.COMPLETE_AT, priority=0,
                        results=0, submitted_at=self.SUBMITTED_AT
                        ))
        d.addCallback(check)
        return d

    def test_downloadArtifactReusingBuild(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="A", complete=1, results=0),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="B", complete=1, results=0,
                                     submitted_at=1418823086, complete_at=1418823086),
                 fakedb.BuildRequest(id=3, buildsetid=3, buildername="B", complete=1, results=0,
                                     submitted_at=self.SUBMITTED_AT_EPOCH, complete_at=self.COMPLETE_AT_EPOCH,
                                     triggeredbybrid=1, startbrid=1, artifactbrid=2)
                 ]
        d = self.insertTestData(breqs)
        d.addCallback(lambda _ :
                self.db.buildrequests.getBuildRequestTriggered(triggeredbybrid=1, buildername='B'))

        def check(brdict):
            self.assertEqual(brdict,
                    dict(artifactbrid=None, brid=2, buildername="B", buildsetid=2,
                        complete=True, complete_at=datetime.datetime(2014, 12, 17, 13, 31, 26, tzinfo=UTC), priority=0,
                        results=0, submitted_at=datetime.datetime(2014, 12, 17, 13, 31, 26, tzinfo=UTC)
                        ))
        d.addCallback(check)
        return d

    def test_getBuildRequestsTriggeredBy(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="A", complete=1, results=0),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="B", complete=1, results=0,
                                     submitted_at=self.SUBMITTED_AT_EPOCH, complete_at=self.COMPLETE_AT_EPOCH,
                                     triggeredbybrid=1, startbrid=1),
                 fakedb.BuildRequest(id=3, buildsetid=2, buildername="B", complete=1, results=0,
                                     submitted_at=self.SUBMITTED_AT_EPOCH, complete_at=self.COMPLETE_AT_EPOCH,
                                     triggeredbybrid=1, startbrid=1)
                 ]
        d = self.insertTestData(breqs)
        d.addCallback(lambda _:
                      self.db.buildrequests.getBuildRequestsTriggeredBy(triggeredbybrid=1, buildername='B'))

        def check(breqs):
            brids = [i['brid'] for i in breqs]
            self.assertEqual(sorted(brids), [2,3])

        d.addCallback(check)
        return d

    def test_getBuildRequestsFilteredBySourceStampsFound(self):
        d = self.buildRequestWithSources(complete=0, results=-1)
        sources = [{'b_codebase': '1', 'b_revision': 'a', 'b_sourcestampsetid': 2, 'b_branch': 'master'},
                   {'b_codebase': '2', 'b_revision': 'b', 'b_sourcestampsetid': 2, 'b_branch': 'staging'}]

        d.addCallback(lambda _: self.db.buildrequests.getBuildRequests(buildername='builder',
                                                                        claimed=False,
                                                                        sourcestamps=sources,
                                                                        sorted=True))

        def check(brdict):
            self.assertEqual(brdict[0]['brid'], 1)

        d.addCallback(check)

        return d

    def test_getBuildRequestsFilteredBySourceStampsNotMatched(self):
        d = self.buildRequestWithSources(complete=0, results=-1)
        sources = [{'b_codebase': '1', 'b_revision': 'a', 'b_sourcestampsetid': 2, 'b_branch': 'master'},
                   {'b_codebase': '2', 'b_revision': 'b', 'b_sourcestampsetid': 2, 'b_branch': 'dev'}]

        d.addCallback(lambda _: self.db.buildrequests.getBuildRequests(buildername='builder',
                                                                        claimed=False,
                                                                        sourcestamps=sources,
                                                                        sorted=True))

        def check(brdict):
            self.assertEqual(brdict, [])
        d.addCallback(check)

        return d

    def test_previousSuccessFullBuildRequestFound(self):
        # add build request
        d = self.buildRequestWithSources()

        sources = [
                {'b_codebase': '1', 'b_revision': 'a', 'b_sourcestampsetid': 2, 'b_branch': 'master'},
                {'b_codebase': '2', 'b_revision': 'b', 'b_sourcestampsetid': 2, 'b_branch': 'staging'}
                ]

        d.addCallback(lambda _ :
                self.db.buildrequests.getBuildRequestBySourcestamps(buildername='builder', sourcestamps = sources))
        def check(brdict):
            self.assertEqual(brdict,
                    dict(artifactbrid=None, brid=1, buildername="builder", buildsetid=1,
                        complete=True, complete_at=self.COMPLETE_AT, priority=0,
                        results=0, submitted_at=self.SUBMITTED_AT
                        ))
        d.addCallback(check)
        return d

    def test_previousSuccessFullBuildRequestNotFound(self):
        # add build request
        d = self.buildRequestWithSources()

        sources = [
                {'b_codebase': '1', 'b_revision': 'z', 'b_sourcestampsetid': 2, 'b_branch': 'master'},
                {'b_codebase': '2', 'b_revision': 'b', 'b_sourcestampsetid': 2, 'b_branch': 'dev'}
                ]

        d.addCallback(lambda _ :
                self.db.buildrequests.getBuildRequestBySourcestamps(buildername='builder', sourcestamps = sources))
        def check(brdict):
            self.assertEqual(brdict, None)
        d.addCallback(check)
        return d

    def test_updateMergedBuildRequests(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="builder"),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="builder"),
                 fakedb.BuildRequest(id=3, buildsetid=3, buildername="builder")]
        d = self.insertTestData(breqs)

        def checkBuildRequest(brlist, value=[None, None]):
            self.assertEqual([br['artifactbrid'] for br in brlist], value)

        def check(rowupdated):
            self.assertEqual(rowupdated, 2)

        # initially it does not have any artifact
        d.addCallback(lambda _ :
                self.db.buildrequests.getBuildRequests(brids=[2,3]))
        d.addCallback(checkBuildRequest, value=[None, None])

        # set the artifact for the merged buildrequests
        d.addCallback(lambda _ : self.db.buildrequests.updateMergedBuildRequest(breqs))
        d.addCallback(check)
        d.addCallback(lambda _ :
                self.db.buildrequests.getBuildRequests(brids=[2,3]))
        d.addCallback(checkBuildRequest, value=[1, 1])

        return d

    def test_reusePreviousBuild(self):
        d = self.buildRequestWithSources()
        breqs = [fakedb.BuildRequest(id=2, buildsetid=2, buildername="builder"),
                 fakedb.BuildRequest(id=3, buildsetid=3, buildername="builder"),
                 fakedb.BuildRequest(id=4, buildsetid=4, buildername="builder")]

        def check(rowupdated):
            self.assertEqual(rowupdated, 3)

        def checkBuildRequests(brlist, artifactbrid=None):
            self.assertTrue(all([br['artifactbrid'] == artifactbrid for br in brlist]))

        d.addCallback(lambda _ : self.insertTestData(breqs))
        d.addCallback(lambda _:
                      self.db.buildrequests.getBuildRequests(brids=[2, 3, 4]))
        d.addCallback(checkBuildRequests)
        d.addCallback(lambda _ :
                      self.db.buildrequests.reusePreviousBuild(breqs, 1))

        d.addCallback(check)
        d.addCallback(lambda _:
                      self.db.buildrequests.getBuildRequests(brids=[2, 3, 4]))
        d.addCallback(checkBuildRequests, artifactbrid=1)

        return d

    def test_updateMergedBuildRequest(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="builder"),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="builder"),
                 fakedb.BuildRequest(id=3, buildsetid=3, buildername="builder"),
                 fakedb.BuildRequest(id=4, buildsetid=4, buildername="builder")]

        d = self.insertTestData(breqs)

        def checkBuildRequests(brlist, artifactbrid=None):
            self.assertEqual(brlist[0]['artifactbrid'], None)
            self.assertTrue(all([br['artifactbrid'] == artifactbrid for br in brlist[1:]]))

        def check(rowupdated):
            self.assertEqual(rowupdated, 3)

        d.addCallback(lambda _:
                      self.db.buildrequests.getBuildRequests(brids=[1, 2, 3, 4]))
        d.addCallback(checkBuildRequests)
        d.addCallback(lambda _:
                      self.db.buildrequests.updateMergedBuildRequest(breqs))

        d.addCallback(check)
        d.addCallback(lambda _:
                      self.db.buildrequests.getBuildRequests(brids=[1, 2, 3, 4]))
        d.addCallback(checkBuildRequests, 1)

        return d

    def test_mergePendingBuildRequests(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="builder"),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="builder"),
                 fakedb.BuildRequest(id=3, buildsetid=3, buildername="builder"),
                 fakedb.BuildRequest(id=4, buildsetid=4, buildername="builder")]

        d = self.insertTestData(breqs)

        def checkBuildRequests(brlist, mergebrid):
            self.assertEqual(brlist[0]['mergebrid'], None)
            self.assertTrue(all([br['mergebrid'] == mergebrid for br in brlist[1:]]))

        d.addCallback(lambda _:
                      self.db.buildrequests.mergePendingBuildRequests([1, 2, 3, 4]))

        d.addCallback(lambda _:
                      self.db.buildrequests.getBuildRequests(brids=[1, 2, 3, 4]))

        d.addCallback(checkBuildRequests, 1)
        return d

    def test_findCompatibleFinishedBuildRequest(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="B", complete=1, results=0,
                                     submitted_at=1418823086, complete_at=1418823086),
                fakedb.BuildRequest(id=2, buildsetid=2, buildername="builder", complete=1, results=0,
                                     submitted_at=1418823086, complete_at=1418823086, startbrid=1),
                fakedb.BuildRequest(id=4, buildsetid=4, buildername="builder", complete=1, results=0,
                                     submitted_at=1418823086, complete_at=1418823086),
                fakedb.BuildRequest(id=5, buildsetid=5, buildername="builder", startbrid=1)]

        d = self.insertTestData(breqs)

        def checkBuildRequest(brdict):
            self.assertEqual(brdict['brid'], 2)

        d.addCallback(lambda _:
                      self.db.buildrequests.findCompatibleFinishedBuildRequest(buildername="builder", startbrid=1))

        d.addCallback(checkBuildRequest)
        return d

    def mergeBuildRequestFinishedBuild(self):
        return [fakedb.BuildRequest(id=1, buildsetid=1, buildername="B", complete=1, results=0,
                                    submitted_at=1418823086, complete_at=1418823086),
                fakedb.BuildRequest(id=2, buildsetid=2, buildername="builder", startbrid=1),
                fakedb.BuildRequest(id=3, buildsetid=3, buildername="builder", startbrid=1,
                                    complete=1, results=0,
                                    submitted_at=1418823086, complete_at=1418823086),
                fakedb.BuildRequest(id=4, buildsetid=4, buildername="builder"),
                fakedb.BuildRequest(id=5, buildsetid=5, buildername="builder"),
                fakedb.BuildRequest(id=6, buildsetid=6, buildername="builder", startbrid=1),
                fakedb.BuildRequest(id=7, buildsetid=7, buildername="builder", startbrid=1)]

    def test_mergeFinishedBuildRequest(self):
        breqs = self.mergeBuildRequestFinishedBuild()

        build = [fakedb.Build(id=1, number=1, brid=3, start_time=1418823086, finish_time=1418823086)]

        d = self.insertTestData(breqs + build)

        def checkBuildRequests(brlist, finished_brid):
            self.assertTrue(all([br['mergebrid'] == finished_brid and br['artifactbrid'] == finished_brid
                                 for br in brlist]))

        def checkBuild(bdict):
            self.assertEqual(bdict, [dict(bid=2,
                                         brid=2,
                                         finish_time=datetime.datetime(2014, 12, 17, 13, 31, 26, tzinfo=UTC),
                                         number=1,
                                         start_time=datetime.datetime(2014, 12, 17, 13, 31, 26, tzinfo=UTC))])
            self.assertTrue(True)

        d.addCallback(lambda _: self.db.buildrequests.findCompatibleFinishedBuildRequest(buildername="builder",
                                                                                         startbrid=1))

        d.addCallback(lambda brdict:
                      self.db.buildrequests.mergeFinishedBuildRequest(brdict,
                                                                      merged_brids=[2, 6, 7],
                                                                      queue=Queue.unclaimed))

        d.addCallback(lambda _: self.db.buildrequests.getBuildRequests(buildername='builder', brids=[2, 6, 7]))

        d.addCallback(checkBuildRequests, finished_brid=3)
        d.addCallback(lambda  _: self.db.builds.getBuildsForRequest(brid=2))
        d.addCallback(checkBuild)
        return d

    def test_mergeFinishedBuildRequestReuseArtifact(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="B", complete=1, results=0,
                                    submitted_at=1418823086, complete_at=1418823086),
                fakedb.BuildRequest(id=2, buildsetid=2, buildername="builder",
                                    complete=1, results=0,
                                    submitted_at=1418823086, complete_at=1418823086),
                fakedb.BuildRequest(id=3, buildsetid=3, buildername="builder", startbrid=1,
                                    complete=1, results=0,
                                    submitted_at=1418823086, complete_at=1418823086, mergebrid=2, artifactbrid=2),
                fakedb.BuildRequest(id=4, buildsetid=4, buildername="builder"),
                fakedb.BuildRequest(id=5, buildsetid=5, buildername="builder"),
                fakedb.BuildRequest(id=6, buildsetid=6, buildername="builder", startbrid=1),
                fakedb.BuildRequest(id=7, buildsetid=7, buildername="builder", startbrid=1)]

        build = [fakedb.Build(id=1, number=1, brid=3, start_time=1418823086, finish_time=1418823086)]

        d = self.insertTestData(breqs + build)

        def checkBuildRequests(brlist, finished_brid, artifactbrid):
            self.assertTrue(all([br['mergebrid'] == finished_brid and br['artifactbrid'] == artifactbrid
                                 for br in brlist]))

        def checkBuild(bdict):
            self.assertEqual(bdict, [dict(bid=3,
                                         brid=7,
                                         finish_time=datetime.datetime(2014, 12, 17, 13, 31, 26, tzinfo=UTC),
                                         number=1,
                                         start_time=datetime.datetime(2014, 12, 17, 13, 31, 26, tzinfo=UTC))])

        d.addCallback(lambda _: self.db.buildrequests.findCompatibleFinishedBuildRequest(buildername="builder",
                                                                                         startbrid=1))

        d.addCallback(lambda brdict:
                      self.db.buildrequests.mergeFinishedBuildRequest(brdict,
                                                                      merged_brids=[6, 7],
                                                                      queue=Queue.unclaimed))

        d.addCallback(lambda _: self.db.buildrequests.getBuildRequests(buildername='builder', brids=[6, 7]))

        d.addCallback(checkBuildRequests, finished_brid=3, artifactbrid=2)
        d.addCallback(lambda  _: self.db.builds.getBuildsForRequest(brid=7))
        d.addCallback(checkBuild)
        return d

    def test_mergeBuildingRequest(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="builder"),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="builder"),
                 fakedb.BuildRequest(id=3, buildsetid=3, buildername="builder"),
                 fakedb.BuildRequest(id=4, buildsetid=4, buildername="builder")]

        breqsclaims = [fakedb.BuildRequestClaim(brid=1, objectid=self.MASTER_ID,
                    claimed_at=1300103810)]

        build = [fakedb.Build(id=1, number=1, brid=1, start_time=1418823086)]

        brids =  [2, 3, 4]

        def checkBuild(bdict):
            self.assertEqual(bdict[0]['bid'], 4)
            self.assertEqual(bdict[0]['brid'], 4)
            self.assertEqual(bdict[0]['number'], 1)

        def check(_, brids):
            def thd(conn):
                claims_tbl = self.db.model.buildrequest_claims
                q = sa.select([claims_tbl.c.brid])\
                    .where(
                        (claims_tbl.c.brid.in_(brids)))
                results = conn.execute(q).fetchall()
                self.assertEqual(sorted([row.brid for row in results]), sorted(brids))
            return self.db.pool.do(thd)

        d = self.insertTestData(breqs + breqsclaims + build)
        d.addCallback(lambda _: self.db.buildrequests.mergeBuildingRequest(breqs, brids,
                                                                           number=1,
                                                                           queue=Queue.unclaimed))

        d.addCallback(lambda _: self.db.builds.getBuildsForRequest(brid=4))
        d.addCallback(checkBuild)
        d.addCallback(check, brids=brids)
        return d

    def test_getBuildRequestCalculateBuildChain(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="builder"),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="builder-02", triggeredbybrid=1, startbrid=1),
                 fakedb.BuildRequest(id=3, buildsetid=3, buildername="builder-03", triggeredbybrid=1, startbrid=1),
                 fakedb.BuildRequest(id=4, buildsetid=4, buildername="builder-02",
                                     triggeredbybrid=3, startbrid=1, mergebrid=2),
                 fakedb.BuildRequest(id=5, buildsetid=5, buildername="builder-04", triggeredbybrid=2, startbrid=1),
                 fakedb.BuildRequest(id=6, buildsetid=6, buildername="builder-05", triggeredbybrid=3, startbrid=1),
                 fakedb.BuildRequest(id=7, buildsetid=7, buildername="builder-06", triggeredbybrid=3, startbrid=1),
                 fakedb.BuildRequest(id=8, buildsetid=8, buildername="builder-07", triggeredbybrid=3, startbrid=1,
                                     complete=1),
                 fakedb.BuildRequest(id=9, buildsetid=9, buildername="builder-08", triggeredbybrid=7, startbrid=1),
                 fakedb.BuildRequest(id=10, buildsetid=10, buildername="builder-09", triggeredbybrid=1, startbrid=1),
                 fakedb.BuildRequest(id=11, buildsetid=11, buildername="builder-10", triggeredbybrid=10, startbrid=1),
                 fakedb.BuildRequest(id=12, buildsetid=12, buildername="builder-03",
                                     triggeredbybrid=1, startbrid=1,  mergebrid=3)]

        builds = [fakedb.Build(id=1, number=1, brid=1, start_time=1418823086),
                  fakedb.Build(id=2, number=2, brid=3, start_time=1418823086),
                  fakedb.Build(id=3, number=3, brid=6, start_time=1418823086),
                  fakedb.Build(id=5, number=5, brid=9, start_time=1418823086),
                  fakedb.Build(id=4, number=4, brid=8, start_time=1418823086)]

        d = self.insertTestData(breqs + builds)

        def checkBuildChain(buildChain, exp_chain=[]):
            self.assertEqual(buildChain, exp_chain)

        d.addCallback(lambda _: self.db.buildrequests.getBuildRequestBuildChain(1))
        d.addCallback(checkBuildChain, exp_chain=[{'buildername': 'builder-02', 'number': None,
                                                   'results': -1, 'brid': 2},
                                                  {'buildername': 'builder-03', 'number': 2,
                                                   'results': -1, 'brid': 3},
                                                  {'buildername': 'builder-04', 'number': None,
                                                   'results': -1, 'brid': 5},
                                                  {'buildername': 'builder-05', 'number': 3,
                                                   'results': -1, 'brid': 6},
                                                  {'buildername': 'builder-06', 'number': None,
                                                   'results': -1, 'brid': 7},
                                                  {'buildername': 'builder-08', 'number': 5,
                                                   'results': -1, 'brid': 9},
                                                  {'buildername': 'builder-09', 'number': None,
                                                   'results': -1, 'brid': 10},
                                                  {'buildername': 'builder-10', 'number': None,
                                                   'results': -1, 'brid': 11}])

        return d

    def fakeRequest(self, brid, bsid, results, buildername='bldr1', complete=False, priority=0, submitted_at=None):
        return {'slavepool': None,
                'artifactbrid': None,
                'buildername': buildername,
                'claimed_at': None,
                'results': results,
                'mine': False,
                'triggeredbybrid': None,
                'submitted_at': epoch2datetime(submitted_at) if submitted_at else None,
                'claimed': False,
                'complete': complete,
                'complete_at': None,
                'buildsetid': bsid,
                'priority': priority,
                'mergebrid': None,
                'brid': brid,
                'startbrid': None}

    def test_getBuildRequestInQueue(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="bldr1"),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="bldr2"),
                 fakedb.BuildRequest(id=3, buildsetid=3, buildername="bldr1", results=RESUME, complete=0),
                 fakedb.BuildRequest(id=4, buildsetid=4, buildername="bldr1", results=0, complete=1),
                 fakedb.BuildRequest(id=5, buildsetid=5, buildername="bldr1", results=RESUME, complete=0, mergebrid=3)]

        breqsclaims = [fakedb.BuildRequestClaim(brid=3, objectid=self.MASTER_ID, claimed_at=1300103810),
                       fakedb.BuildRequestClaim(brid=4, objectid=self.MASTER_ID, claimed_at=1300103810),
                       fakedb.BuildRequestClaim(brid=5, objectid=self.MASTER_ID, claimed_at=1300103810)]

        d = self.insertTestData(breqs + breqsclaims)
        d.addCallback(lambda _: self.db.buildrequests.getBuildRequestInQueue(buildername="bldr1"))
        d.addCallback(lambda queue: self.assertEqual(queue, [self.fakeRequest(1, 1, BEGINNING),
                                                             self.fakeRequest(3, 3, RESUME)]))
        return d

    def insertBuildRequestsInQueue(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="bldr1", priority=20, submitted_at=1450171024),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="bldr2", priority=50, submitted_at=1450171039),
                 fakedb.BuildRequest(id=3, buildsetid=3, buildername="bldr1", results=RESUME,
                                     complete=0, priority=100, submitted_at=1449668061),
                 fakedb.BuildRequest(id=4, buildsetid=4, buildername="bldr1", results=0, complete=1, priority=75,
                                     submitted_at=1450451019,),
                 fakedb.BuildRequest(id=5, buildsetid=5, buildername="bldr1", results=RESUME, complete=0, mergebrid=3),
                 fakedb.BuildRequest(id=6, buildsetid=6, buildername="bldr1", priority=100, submitted_at=1449579016),
                 fakedb.BuildRequest(id=7, buildsetid=7, buildername="bldr1", results=RESUME, complete=0,
                                     priority=50, submitted_at=1449579016),
                 fakedb.BuildRequest(id=8, buildsetid=8, buildername="bldr1", priority=30, submitted_at=1450171024)]

        breqsclaims = [fakedb.BuildRequestClaim(brid=id, objectid=self.MASTER_ID, claimed_at=1300103810)
                       for id in range(3, 8)]

        breqs_sourcestamps = []
        ssid = 1
        for id in range(1, 9):
            breqs_sourcestamps.append(fakedb.SourceStampSet(id=id))
            breqs_sourcestamps.append(fakedb.Buildset(id=id, sourcestampsetid=id))
            breqs_sourcestamps.append(fakedb.SourceStamp(id=ssid,
                                                         revision='a%d' % id,
                                                         codebase='1',
                                                         sourcestampsetid=id,
                                                         branch='master',
                                                         repository='z'))
            breqs_sourcestamps.append(fakedb.SourceStamp(id=ssid+1,
                                                         revision='b%d' % id,
                                                         codebase='2',
                                                         sourcestampsetid=id,
                                                         branch='5.2/staging',
                                                         repository='w'))
            ssid+=2

        d = self.insertTestData(breqs + breqsclaims + breqs_sourcestamps)
        return d

    def test_getBuildRequestInQueueCodebasesFound(self, filter = None):
        expectedBreqs = [self.fakeRequest(brid=8, bsid=8, results=BEGINNING, priority=30, submitted_at=1450171024),
                         self.fakeRequest(brid=1, bsid=1, results=BEGINNING, priority=20, submitted_at=1450171024),
                         self.fakeRequest(brid=3, bsid=3, results=RESUME, priority=100, submitted_at=1449668061),
                         self.fakeRequest(brid=7, bsid=7, results=RESUME, priority=50, submitted_at=1449579016)]

        sourcestamps_filter = [{'b_codebase': '1', 'b_branch': 'master'},
                               {'b_codebase': '2', 'b_branch': '5.2/staging'}] if filter is None else filter

        def checkResults(buildqueue):
            self.assertEquals(buildqueue, expectedBreqs)

        d = self.insertBuildRequestsInQueue()
        d.addCallback(lambda _: self.db.buildrequests.getBuildRequestInQueue(buildername="bldr1",
                                                                            sourcestamps=sourcestamps_filter,
                                                                            sorted=True))
        d.addCallback(checkResults)
        return d

    def test_getBuildRequestInQueueCodebasesNotFound(self):
        sourcestamps_filter = [{'b_codebase': '1', 'b_branch': 'master'},
                               {'b_codebase': '2', 'b_branch': 'staging'}]

        d = self.insertBuildRequestsInQueue()
        d.addCallback(lambda _: self.db.buildrequests.getBuildRequestInQueue(buildername="bldr1",
                                                                            sourcestamps=sourcestamps_filter,
                                                                            sorted=True))
        d.addCallback(lambda res: self.assertEquals(res, []))
        return d

    def test_getBuildRequestInQueueSingleCodebaseFilter(self):
        sourcestamps_filter = [{'b_codebase': '1', 'b_branch': 'master'}]
        d =  self.test_getBuildRequestInQueueCodebasesFound(filter=sourcestamps_filter)
        return d

    def insertPrioritizedBreqs(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="bldr1",
                                     priority=20, submitted_at=1450171024),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="bldr1",
                                     priority=50, submitted_at=1450171039),
                 fakedb.BuildRequest(id=3, buildsetid=3, buildername="bldr2",
                                     priority=100, submitted_at=1449668061,
                                     startbrid=1),
                 fakedb.BuildRequest(id=4, buildsetid=4, buildername="bldr1",
                                     priority=20,submitted_at=1449579016,
                                     results=RESUME, complete=0),
                 fakedb.BuildRequest(id=5, buildsetid=5, buildername="bldr1",
                                     priority=75, submitted_at=1450451019,
                                     results=RESUME, complete=0),
                 fakedb.BuildRequest(id=6, buildsetid=6, buildername="bldr3",
                                     priority=100, submitted_at=1446632022,
                                     results=RESUME, complete=0),
                 fakedb.BuildRequest(id=7, buildsetid=7, buildername="bldr3",
                                     priority=100, submitted_at=1446632022,
                                     results=RESUME, complete=0, mergebrid=7),
                 fakedb.BuildRequest(id=8, buildsetid=8, buildername="bldr2",
                                     priority=100, submitted_at=1449668061),
                 fakedb.BuildRequest(id=9, buildsetid=9, buildername="bldr1",
                                     priority=100, submitted_at=1449579016),
                 fakedb.BuildRequest(id=10, buildsetid=10, buildername="bldr1",
                                     priority=100, submitted_at=1449579016, results=RESUME, complete=0)]

        breqsclaims = [fakedb.BuildRequestClaim(brid=8, objectid=self.MASTER_ID, claimed_at=1300103810),
                       fakedb.BuildRequestClaim(brid=4, objectid=self.MASTER_ID, claimed_at=1300103810),
                       fakedb.BuildRequestClaim(brid=5, objectid=self.MASTER_ID, claimed_at=1300103810),
                       fakedb.BuildRequestClaim(brid=6, objectid=self.MASTER_ID, claimed_at=1300103810),
                       fakedb.BuildRequestClaim(brid=7, objectid=self.MASTER_ID, claimed_at=1300103810),
                       fakedb.BuildRequestClaim(brid=10, objectid=self.MASTER_ID, claimed_at=1300103810)]

        breqsprop = [fakedb.BuildsetProperty(buildsetid=2,
                                             property_name='selected_slave',
                                             property_value='["build-slave-03", "Force Build Form"]'),
                     fakedb.BuildsetProperty(buildsetid=6,
                                             property_name='selected_slave',
                                             property_value='["build-slave-02", "Force Build Form"]')]

        d = self.insertTestData(breqs + breqsclaims + breqsprop)
        return d

    def fakePrioritzedRequest(self, brid, buildername, priority, submitted_at,
                              selected_slave, results, slavepool, startbrid=None):
        return {'brid': brid,
                'buildsetid': brid,
                'buildername': buildername,
                'priority': priority,
                'submitted_at': epoch2datetime(submitted_at),
                'selected_slave': selected_slave,
                'results': results,
                'slavepool': slavepool,
                'startbrid': startbrid
                }

    def test_getPrioritizedBuildRequestsInUnclaimedQueue(self):
        expectedBreqs = [self.fakePrioritzedRequest(brid=9, results=-1,
                                                    buildername='bldr1', priority=100,
                                                    submitted_at=1449579016,
                                                    selected_slave=None, slavepool=None),
                         self.fakePrioritzedRequest(brid=3, results=-1,
                                                    buildername='bldr2', priority=100,
                                                    submitted_at=1449668061,
                                                    selected_slave=None,
                                                    slavepool=None, startbrid=1),
                         self.fakePrioritzedRequest(brid=2, results=-1,
                                                    buildername='bldr1', priority=50,
                                                    submitted_at=1450171039,
                                                    selected_slave="build-slave-03", slavepool=None),
                         self.fakePrioritzedRequest(brid=1, results=-1,
                                                    buildername='bldr1', priority=20,
                                                    submitted_at=1450171024,
                                                    selected_slave=None, slavepool=None)]

        d = self.insertPrioritizedBreqs()
        d.addCallback(lambda _: self.db.buildrequests.getBuildRequestsInQueue(queue=Queue.unclaimed))
        d.addCallback(lambda queue: self.assertEqual(queue, expectedBreqs))
        return d


    def test_getPrioritizedBuildRequestsInResumeQueue(self):
        expectedBreqs = [self.fakePrioritzedRequest(brid=6, results=RESUME,
                                     buildername='bldr3', priority=100,
                                     submitted_at=1446632022,
                                     selected_slave="build-slave-02", slavepool=None),
                         self.fakePrioritzedRequest(brid=10, results=RESUME,
                                     buildername='bldr1', priority=100,
                                     submitted_at=1449579016,
                                     selected_slave=None, slavepool=None),
                         self.fakePrioritzedRequest(brid=5, results=RESUME,
                                     buildername='bldr1', priority=75,
                                     submitted_at=1450451019,
                                     selected_slave=None, slavepool=None),
                         self.fakePrioritzedRequest(brid=4, results=RESUME,
                                     buildername='bldr1', priority=20,
                                     submitted_at=1449579016,
                                     selected_slave=None, slavepool=None)]

        d = self.insertPrioritizedBreqs()
        d.addCallback(lambda _: self.db.buildrequests.getBuildRequestsInQueue(queue=Queue.resume))
        d.addCallback(lambda queue: self.assertEqual(queue, expectedBreqs))
        return d

    @defer.inlineCallbacks
    def test_getPrioritizedBuildRequestsInUnclaimedQueueUsesFilters(self):
        sources = [{'repository': 'repo1', 'codebase': 'cb1', 'branch': 'master', 'revision': 'asz3113'},
                   {'repository': 'repo2', 'codebase': 'cb2', 'branch': 'develop', 'revision': 'asz3114'}]

        sourcestamps = []
        testdata = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="bldr1",
                                        priority=20, submitted_at=1450171024),
                    fakedb.BuildRequest(id=2, buildsetid=2, buildername="bldr1",
                                        priority=20, submitted_at=1450171024, mergebrid=1),
                    fakedb.BuildRequest(id=3, buildsetid=3, buildername="bldr1",
                                        priority=20, submitted_at=1450171024),
                    fakedb.BuildRequest(id=4, buildsetid=4, buildername="bldr2",
                                        priority=20, submitted_at=1450171024)]

        testdata += [fakedb.Buildset(id=2, sourcestampsetid=2)]
        testdata += [fakedb.SourceStampSet(id=2)]

        for ss in sources:
            testdata += [fakedb.SourceStamp(sourcestampsetid=2,
                                            repository=ss['repository'],
                                            codebase=ss['codebase'],
                                            branch=ss['branch'],
                                            revision=ss['revision'])]

            sourcestamps.append({'b_codebase': ss['codebase'],
                                 'b_revision': ss['revision'],
                                 'b_branch': ss['branch'],
                                 'b_sourcestampsetid': 1})

        self.insertTestData(testdata)
        result = yield self.db.buildrequests.getBuildRequestsInQueue(queue=Queue.unclaimed,
                                                                     buildername='bldr1',
                                                                     mergebrids=[1],
                                                                     sourcestamps=sourcestamps)
        self.assertTrue(len(result) == 1)
        self.assertTrue(result[0]['brid'] ==  2)


    def checkCanceledBuildRequests(self, brlist, complete=True, results=CANCELED):
        self.assertTrue(all([br['complete'] == complete and br['results'] == results
                             and (br['complete_at'] is not None if complete else br['complete_at'] is None)
                             for br in brlist]))

    def test_cancelBuildRequestsByBuildNumber(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="bldr1",
                                     priority=20, submitted_at=1450171024),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="bldr2",
                                     priority=50, submitted_at=1450171039),
                 fakedb.BuildRequest(id=3, buildsetid=3, buildername="bldr1",
                                     priority=100, submitted_at=1449668061, mergebrid=1),
                 fakedb.BuildRequest(id=4, buildsetid=4, buildername="bldr1",
                                     priority=20,submitted_at=1449579016,
                                     results=RESUME, complete=0, mergebrid=1),
                 fakedb.BuildRequest(id=5, buildsetid=5, buildername="bldr1",
                                     priority=50, submitted_at=1450171039, mergebrid=1),
                 fakedb.BuildRequest(id=6, buildsetid=6, buildername="bldr1", priority=50,
                                     submitted_at=1450171039)]

        build = [fakedb.Build(id=50, brid=1, number=5, start_time=1304262222,
                              finish_time=1452520540, slavename="build-slave-01"),
                 fakedb.Build(id=51, brid=3, number=5, start_time=1304262222, finish_time=1452520540),
                 fakedb.Build(id=52, brid=5, number=5, start_time=1304262222, finish_time=1452520540),
                 fakedb.Build(id=53, brid=1, number=5, start_time=1304262222, slavename="build-slave-02"),
                 fakedb.Build(id=54, brid=3, number=5, start_time=1304262222),
                 fakedb.Build(id=55, brid=4, number=5, start_time=1304262222),
                 fakedb.Build(id=56, brid=5, number=5, start_time=1304262222),
                 fakedb.Build(id=49, brid=2, number=5, start_time=1304262222),
                 fakedb.Build(id=57, brid=6, number=6, start_time=1304262222)]

        d = self.insertTestData(breqs + build)
        d.addCallback(lambda _: self.db.buildrequests.cancelBuildRequestsByBuildNumber(number=5, buildername="bldr1"))
        d.addCallback(lambda _: self.db.buildrequests.getBuildRequests(buildername='bldr1', brids=[1, 3, 4, 5]))
        d.addCallback(self.checkCanceledBuildRequests)
        d.addCallback(lambda _: self.db.buildrequests.getBuildRequests(buildername='bldr1', brids=[6]))
        d.addCallback(self.checkCanceledBuildRequests, complete=False, results=-1)
        d.addCallback(lambda _: self.db.buildrequests.getBuildRequests(buildername='bldr2', brids=[2]))
        d.addCallback(self.checkCanceledBuildRequests, complete=False, results=-1)
        return d

    def test_cancelResumeBuildRequests(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="bldr1",
                                     priority=20, submitted_at=1450171024),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="bldr1",
                                     priority=50, results=RESUME, submitted_at=1450171039),
                 fakedb.BuildRequest(id=3, buildsetid=3, buildername="bldr1",
                                     priority=100, results=RESUME, submitted_at=1449668061, mergebrid=2),
                 fakedb.BuildRequest(id=4, buildsetid=4, buildername="bldr1",
                                     priority=20,submitted_at=1449579016, results=RESUME)]

        d = self.insertTestData(breqs)
        d.addCallback(lambda _:  self.db.buildrequests.cancelResumeBuildRequest(brid=2))
        d.addCallback(lambda _: self.db.buildrequests.getBuildRequests(buildername='bldr1', brids=[2, 3]))
        d.addCallback(self.checkCanceledBuildRequests)
        d.addCallback(lambda _: self.db.buildrequests.getBuildRequests(buildername='bldr1', brids=[1]))
        d.addCallback(self.checkCanceledBuildRequests, complete=False, results=-1)
        d.addCallback(lambda _: self.db.buildrequests.getBuildRequests(buildername='bldr1', brids=[4]))
        d.addCallback(self.checkCanceledBuildRequests, complete=False, results=RESUME)
        return d
