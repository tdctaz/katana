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

import itertools
import sqlalchemy as sa
from twisted.internet import reactor
from twisted.python import log
from buildbot.db import base
from buildbot.util import epoch2datetime, datetime2epoch

class AlreadyClaimedError(Exception):
    pass

class NotClaimedError(Exception):
    pass

class BrDict(dict):
    pass

def mkdt(epoch):
    if epoch:
        return epoch2datetime(epoch)

# private decorator to add a _master_objectid keyword argument, querying from
# the master
def with_master_objectid(fn):
    def wrap(self, *args, **kwargs):
        d = self.db.master.getObjectId()
        d.addCallback(lambda master_objectid :
                fn(self, _master_objectid=master_objectid, *args, **kwargs))
        return d
    wrap.__name__ = fn.__name__
    wrap.__doc__ = fn.__doc__
    return wrap

class BuildRequestsConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/database.rst

    @with_master_objectid
    def getBuildRequest(self, brid, _master_objectid=None):
        def thd(conn):
            reqs_tbl = self.db.model.buildrequests
            claims_tbl = self.db.model.buildrequest_claims
            res = conn.execute(sa.select([
                reqs_tbl.outerjoin(claims_tbl,
                                   (reqs_tbl.c.id == claims_tbl.c.brid)) ],
                whereclause=(reqs_tbl.c.id == brid)))
            row = res.fetchone()

            rv = None
            if row:
                rv = self._brdictFromRow(row, _master_objectid)
            res.close()
            return rv
        return self.db.pool.do(thd)

    @with_master_objectid
    def getBuildRequests(self, buildername=None, complete=None, claimed=None,
            bsid=None, _master_objectid=None, brids = None):
        def thd(conn):
            reqs_tbl = self.db.model.buildrequests
            claims_tbl = self.db.model.buildrequest_claims
            q = sa.select([ reqs_tbl.outerjoin(claims_tbl,
                                    reqs_tbl.c.id == claims_tbl.c.brid) ])
            if claimed is not None:
                if not claimed:
                    q = q.where(
                        (claims_tbl.c.claimed_at == None) &
                        (reqs_tbl.c.complete == 0))
                elif claimed == "mine":
                    q = q.where(
                        (claims_tbl.c.objectid == _master_objectid))
                else:
                    q = q.where(
                        (claims_tbl.c.claimed_at != None))
            if buildername is not None:
                q = q.where(reqs_tbl.c.buildername == buildername)
            if complete is not None:
                if complete:
                    q = q.where(reqs_tbl.c.complete != 0)
                else:
                    q = q.where(reqs_tbl.c.complete == 0)
            if bsid is not None:
                q = q.where(reqs_tbl.c.buildsetid == bsid)
            if brids is not None:
                q = q.where(reqs_tbl.c.id.in_(brids))
            res = conn.execute(q)

            return [ self._brdictFromRow(row, _master_objectid)
                     for row in res.fetchall() ]
        return self.db.pool.do(thd)

    def getUnclaimedBuildRequest(self):
        def thd(conn):
            reqs_tbl = self.db.model.buildrequests
            claims_tbl = self.db.model.buildrequest_claims
            buildset_tbl = self.db.model.buildsets

            q = sa.select([reqs_tbl.c.id, reqs_tbl.c.buildername, buildset_tbl.c.reason],
                          from_obj=reqs_tbl.outerjoin(claims_tbl, (reqs_tbl.c.id == claims_tbl.c.brid))
                          .join(buildset_tbl, (reqs_tbl.c.buildsetid == buildset_tbl.c.id)),
                          whereclause=((claims_tbl.c.claimed_at == None) &
                                       (reqs_tbl.c.complete == 0)))
            res = conn.execute(q)
            rows = res.fetchall()
            rv = []
            if rows:
                for row in rows:
                    rv.append(dict(brid=row.id, buildername=row.buildername, reason=row.reason))

            res.close()
            return rv

        return self.db.pool.do(thd)


    def getBuildRequestBySourcestamps(self, buildername=None, sourcestamps = None):
        def thd(conn):
            sourcestampsets_tbl = self.db.model.sourcestampsets
            sourcestamps_tbl = self.db.model.sourcestamps
            buildrequests_tbl = self.db.model.buildrequests
            buildsets_tbl = self.db .model.buildsets
            clauses = []

            # check sourcestampset has same number of row in the sourcestamps table
            stmt = sa.select([sourcestamps_tbl.c.sourcestampsetid]) \
                .where(sourcestamps_tbl.c.sourcestampsetid == sourcestampsets_tbl.c.id) \
                .group_by(sourcestamps_tbl.c.sourcestampsetid) \
                .having(sa.func.count(sourcestamps_tbl.c.id) == len(sourcestamps))

            clauses.append(sourcestampsets_tbl.c.id == stmt)
            clauses.append(sourcestampsets_tbl.c.id != sourcestamps[0]['b_sourcestampsetid'])

            # check that sourcestampset match all revisions x codebases
            for ss in sourcestamps:
                stmt_temp = sa.select([sourcestamps_tbl.c.sourcestampsetid]) \
                    .where(sourcestamps_tbl.c.sourcestampsetid ==  sourcestampsets_tbl.c.id ) \
                    .where(sourcestamps_tbl.c.codebase == ss['b_codebase']) \
                    .where(sourcestamps_tbl.c.revision == ss['b_revision'])\
                    .where(sourcestamps_tbl.c.branch == ss['b_branch'])
                clauses.append(sourcestampsets_tbl.c.id == stmt_temp)

            stmt2 = sa.select(columns=[sourcestampsets_tbl.c.id]) \
                .where(sa.and_(*clauses))

            stmt3 = sa.select(columns=[buildsets_tbl.c.id])\
                        .where(buildsets_tbl.c.sourcestampsetid.in_(stmt2))

            last_br = sa.select(columns=[sa.func.max(buildrequests_tbl.c.id).label("id")])\
                    .where(buildrequests_tbl.c.buildsetid.in_(stmt3))\
                    .where(buildrequests_tbl.c.complete == 1)\
                    .where(buildrequests_tbl.c.results == 0)\
                    .where(buildrequests_tbl.c.buildername == buildername)\
                    .where(buildrequests_tbl.c.artifactbrid == None)

            q = sa.select(columns=[buildrequests_tbl])\
                .where(buildrequests_tbl.c.id == last_br)

            res = conn.execute(q)
            row = res.fetchone()
            buildrequest = None
            if row:
                submitted_at = mkdt(row.submitted_at)
                complete_at = mkdt(row.complete_at)
                buildrequest = dict(brid=row.id, buildsetid=row.buildsetid,
                      buildername=row.buildername, priority=row.priority,
                      complete=bool(row.complete), results=row.results,
                      submitted_at=submitted_at, complete_at=complete_at, artifactbrid=row.artifactbrid)

            res.close()
            return buildrequest
        return self.db.pool.do(thd)

    def reusePreviousBuild(self, requests, artifactbrid):
        def thd(conn):
            buildrequests_tbl = self.db.model.buildrequests
            buildsets_tbl = self.db .model.buildsets

            brids = [br.id for br in requests]
            stmt = buildrequests_tbl.update()\
                .where(buildrequests_tbl.c.id.in_(brids))\
                .values(artifactbrid=artifactbrid)

            res = conn.execute(stmt)
            return res.rowcount

        return self.db.pool.do(thd)

    def updateMergedBuildRequest(self, requests):
        def thd(conn):
            buildrequests_tbl = self.db.model.buildrequests

            mergedrequests = [br.id for br in requests[1:]]

            stmt2 = buildrequests_tbl.update() \
                .where(buildrequests_tbl.c.id.in_(mergedrequests))\
                .values(artifactbrid=requests[0].id)

            res = conn.execute(stmt2)
            return res.rowcount

        return self.db.pool.do(thd)

    def mergeRunningBuildRequest(self, requests):
        def thd(conn):
            buildrequests_tbl = self.db.model.buildrequests
            mergedrequests = [br.id for br in requests[1:]]

            q = sa.select([buildrequests_tbl.c.artifactbrid]) \
                .where(id == requests[0].id)
            res = conn.execute(q)
            row = res.fetchone()
            # by default it will mark using artifact generated from merged brid
            stmt2 = buildrequests_tbl.update() \
                .where(buildrequests_tbl.c.id.in_(mergedrequests)) \
                .values(artifactbrid=requests[0].id)

            if row and (row.artifactbrid is not None):
                stmt2 = buildrequests_tbl.update() \
                .where(buildrequests_tbl.c.id.in_(mergedrequests)) \
                .values(artifactbrid=row.artifactbrid)
            res = conn.execute(stmt2)
            return res.rowcount

        return self.db.pool.do(thd)

    def mergeBuildRequests(self, brid, merged_brids):
        def thd(conn):
            buildrequests_tbl = self.db.model.buildrequests

        return self.db.pool.do(thd)

    def getBuildRequestTriggered(self, triggeredbybrid, buildername):
        def thd(conn):
            buildrequests_tbl = self.db.model.buildrequests

            stmt_br = sa.select([buildrequests_tbl]) \
                .where(buildrequests_tbl.c.buildername == buildername) \
                .where(buildrequests_tbl.c.triggeredbybrid == triggeredbybrid)

            res = conn.execute(stmt_br)
            row = res.fetchone()
            buildrequest = None
            if row:
                if row.artifactbrid:
                    stmt = sa.select([buildrequests_tbl]) \
                        .where(buildrequests_tbl.c.id == row.artifactbrid)
                    res = conn.execute(stmt)
                    br_row = res.fetchone()
                    if br_row:
                        row = br_row

                submitted_at = mkdt(row.submitted_at)
                complete_at = mkdt(row.complete_at)
                buildrequest = dict(brid=row.id, buildsetid=row.buildsetid,
                                    buildername=row.buildername, priority=row.priority,
                                    complete=bool(row.complete), results=row.results,
                                    submitted_at=submitted_at, complete_at=complete_at, artifactbrid=row.artifactbrid)

            res.close()
            return buildrequest

        return self.db.pool.do(thd)

    def updateTriggeredBy(self, triggeredbybrid, bsid):
        def thd(conn):
            buildrequests_tbl = self.db.model.buildrequests

            q = sa.select([buildrequests_tbl.c.triggeredbybrid, buildrequests_tbl.c.startbrid])\
                .where(buildrequests_tbl.c.id == triggeredbybrid)

            res = conn.execute(q)
            row = res.fetchone()

            stmt = buildrequests_tbl.update() \
                .where(buildrequests_tbl.c.buildsetid == bsid) \
                .values(triggeredbybrid=triggeredbybrid)\
                .values(startbrid=triggeredbybrid)

            if row and (row.triggeredbybrid is not None):
                stmt = buildrequests_tbl.update() \
                    .where(buildrequests_tbl.c.buildsetid == bsid) \
                    .values(triggeredbybrid=triggeredbybrid) \
                    .values(startbrid=row.startbrid)

            res = conn.execute(stmt)
            return

        return  self.db.pool.do(thd)

    @with_master_objectid
    def claimBuildRequests(self, brids, claimed_at=None, _reactor=reactor,
                            _master_objectid=None):
        if claimed_at is not None:
            claimed_at = datetime2epoch(claimed_at)
        else:
            claimed_at = _reactor.seconds()

        def thd(conn):
            transaction = conn.begin()
            tbl = self.db.model.buildrequest_claims

            try:
                q = tbl.insert()
                conn.execute(q, [ dict(brid=id, objectid=_master_objectid,
                                    claimed_at=claimed_at)
                                  for id in brids ])
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                transaction.rollback()
                raise AlreadyClaimedError

            transaction.commit()

        return self.db.pool.do(thd)

    @with_master_objectid
    def reclaimBuildRequests(self, brids, _reactor=reactor,
                            _master_objectid=None):
        def thd(conn):
            transaction = conn.begin()
            tbl = self.db.model.buildrequest_claims
            claimed_at = _reactor.seconds()

            # we'll need to batch the brids into groups of 100, so that the
            # parameter lists supported by the DBAPI aren't exhausted
            iterator = iter(brids)

            while 1:
                batch = list(itertools.islice(iterator, 100))
                if not batch:
                    break # success!

                q = tbl.update(tbl.c.brid.in_(batch)
                                & (tbl.c.objectid==_master_objectid))
                res = conn.execute(q, claimed_at=claimed_at)

                # if fewer rows were updated than expected, then something
                # went wrong
                if res.rowcount != len(batch):
                    transaction.rollback()
                    raise AlreadyClaimedError

            transaction.commit()
        return self.db.pool.do(thd)

    @with_master_objectid
    def unclaimBuildRequests(self, brids, _master_objectid=None):
        def thd(conn):
            transaction = conn.begin()
            claims_tbl = self.db.model.buildrequest_claims

            # we'll need to batch the brids into groups of 100, so that the
            # parameter lists supported by the DBAPI aren't exhausted
            iterator = iter(brids)

            while 1:
                batch = list(itertools.islice(iterator, 100))
                if not batch:
                    break # success!

                try:
                    q = claims_tbl.delete(
                            (claims_tbl.c.brid.in_(batch))
                            & (claims_tbl.c.objectid == _master_objectid))
                    conn.execute(q)
                except:
                    transaction.rollback()
                    raise

            transaction.commit()
        return self.db.pool.do(thd)

    @with_master_objectid
    def completeBuildRequests(self, brids, results, complete_at=None,
                            _reactor=reactor, _master_objectid=None):
        if complete_at is not None:
            complete_at = datetime2epoch(complete_at)
        else:
            complete_at = _reactor.seconds()

        def thd(conn):
            transaction = conn.begin()

            # the update here is simple, but a number of conditions are
            # attached to ensure that we do not update a row inappropriately,
            # Note that checking that the request is mine would require a
            # subquery, so for efficiency that is not checed.

            reqs_tbl = self.db.model.buildrequests

            # we'll need to batch the brids into groups of 100, so that the
            # parameter lists supported by the DBAPI aren't exhausted
            iterator = iter(brids)

            while 1:
                batch = list(itertools.islice(iterator, 100))
                if not batch:
                    break # success!

                q = reqs_tbl.update()
                q = q.where(reqs_tbl.c.id.in_(batch))
                q = q.where(reqs_tbl.c.complete != 1)
                res = conn.execute(q,
                    complete=1,
                    results=results,
                    complete_at=complete_at)

                # if an incorrect number of rows were updated, then we failed.
                if res.rowcount != len(batch):
                    log.msg("tried to complete %d buildreqests, "
                        "but only completed %d" % (len(batch), res.rowcount))
                    transaction.rollback()
                    raise NotClaimedError
            transaction.commit()
        return self.db.pool.do(thd)

    def unclaimExpiredRequests(self, old, _reactor=reactor):
        def thd(conn):
            reqs_tbl = self.db.model.buildrequests
            claims_tbl = self.db.model.buildrequest_claims
            old_epoch = _reactor.seconds() - old

            # select any expired requests, and delete each one individually
            expired_brids = sa.select([ reqs_tbl.c.id ],
                        whereclause=(reqs_tbl.c.complete != 1))
            res = conn.execute(claims_tbl.delete(
                        (claims_tbl.c.claimed_at < old_epoch) &
                        claims_tbl.c.brid.in_(expired_brids)))
            return res.rowcount
        d = self.db.pool.do(thd)
        def log_nonzero_count(count):
            if count != 0:
                log.msg("unclaimed %d expired buildrequests (over %d seconds "
                        "old)" % (count, old))
        d.addCallback(log_nonzero_count)
        return d

    def _brdictFromRow(self, row, master_objectid):
        claimed = mine = False
        claimed_at = None
        if row.claimed_at is not None:
            claimed_at = row.claimed_at
            claimed = True
            mine = row.objectid == master_objectid

        submitted_at = mkdt(row.submitted_at)
        complete_at = mkdt(row.complete_at)
        claimed_at = mkdt(row.claimed_at)

        return BrDict(brid=row.id, buildsetid=row.buildsetid,
                buildername=row.buildername, priority=row.priority,
                claimed=claimed, claimed_at=claimed_at, mine=mine,
                complete=bool(row.complete), results=row.results,
                submitted_at=submitted_at, complete_at=complete_at)
