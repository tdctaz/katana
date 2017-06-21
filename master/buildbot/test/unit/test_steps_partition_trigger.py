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

from mock import Mock
from buildbot import config, interfaces
from buildbot.steps import partition_trigger
from buildbot.status import master
from buildbot.status.results import SUCCESS, FAILURE, DEPENDENCY_FAILURE, INTERRUPTED
from buildbot.test.util import steps
from buildbot.test.fake import fakemaster, fakedb, fakebuild
from twisted.trial import unittest
from twisted.internet import defer, reactor
from zope.interface import implements

# Magic numbers that relate brid to other build settings
BRID_TO_BSID = lambda brid: brid+2000
BRID_TO_BID  = lambda brid: brid+3000
BRID_TO_BUILD_NUMBER = lambda brid: brid+4000

class FakeTriggerable():
    implements(interfaces.ITriggerableScheduler)

    def __init__(self, name):
        self.name = name
        self.triggered_with = []
        self.result = SUCCESS
        self.brids = {}
        self.exception = False

    def trigger(self, sourcestamps = None, set_props=None, triggeredbybrid=None, reason=None):
        self.triggered_with.append((sourcestamps, set_props.properties, triggeredbybrid))
        d = defer.Deferred()
        if self.exception:
            reactor.callLater(0, d.errback, RuntimeError('oh noes'))
        else:
            reactor.callLater(0, d.callback, (self.result, self.brids))
        return d

class TestPartitionTrigger(steps.BuildStepMixin, unittest.TestCase):
    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def aExpectTriggeredWith(self, a):
        self.exp_a_trigger = a

    def bExpectTriggeredWith(self, b):
        self.exp_b_trigger = b

    def setupStep(self, step, sourcestampsInBuild=None, gotRevisionsInBuild=None, *args, **kwargs):
        sourcestamps = sourcestampsInBuild or []
        got_revisions = gotRevisionsInBuild or {}

        steps.BuildStepMixin.setupStep(self, step, *args, **kwargs)

        # This step reaches deeply into a number of parts of Buildbot.  That
        # should be fixed!

        # set up a buildmaster that knows about two fake schedulers, a and b
        m = fakemaster.make_master()
        self.build.builder.botmaster = m.botmaster
        m.db = fakedb.FakeDBConnector(self)
        m.status = master.Status(m)
        m.config.buildbotURL = "baseurl/"

        self.scheduler_a = FakeTriggerable(name='a')
        self.scheduler_b = FakeTriggerable(name='b')
        def allSchedulers():
            return [ self.scheduler_a, self.scheduler_b ]
        m.allSchedulers = allSchedulers

        self.scheduler_a.brids = {'A': 11}
        self.scheduler_b.brids = {'B': 22}

        make_fake_br = lambda brid, name: fakedb.BuildRequest(id=brid,
                                                              buildsetid=BRID_TO_BSID(brid),
                                                              buildername=name)
        make_fake_build = lambda brid: fakedb.Build(brid=brid,
                                                    id=BRID_TO_BID(brid),
                                                    number=BRID_TO_BUILD_NUMBER(brid))

        m.db.insertTestData([
               make_fake_br(11, "A"),
               make_fake_br(22, "B"),
               make_fake_build(11),
               make_fake_build(22),
        ])

        def getAllSourceStamps():
            return sourcestamps
        self.build.getAllSourceStamps = getAllSourceStamps
        def getAllGotRevisions():
            return got_revisions
        self.build.build_status.getAllGotRevisions = getAllGotRevisions

        request = Mock()
        request.id = 1

        self.build.requests = [request]

        self.exp_add_sourcestamp = None
        self.exp_a_trigger = []
        self.exp_b_trigger = []
        self.exp_added_urls = []

    def runStep(self, expect_waitForFinish=False):
        d = steps.BuildStepMixin.runStep(self)

        if expect_waitForFinish:
            # the build doesn't finish until after a callLater, so this has the
            # effect of checking whether the deferred has been fired already;
            # it should not have been!
            early = []
            d.addCallback(early.append)
            self.assertEqual(early, [])

        def check(_):
            self.assertEqual(self.scheduler_a.triggered_with, self.exp_a_trigger)
            self.assertEqual(self.scheduler_b.triggered_with, self.exp_b_trigger)
            self.assertEqual(self.step_status.addURL.call_args_list, self.exp_added_urls)

            if self.exp_add_sourcestamp:
                self.assertEqual(self.addSourceStamp_kwargs, self.exp_add_sourcestamp)
        d.addCallback(check)

        # pause runStep's completion until after any other callLater's are done
        def wait(_):
            d = defer.Deferred()
            reactor.callLater(0, d.callback, None)
            return d
        d.addCallback(wait)

        return d

    def test_constructor_whenPartitionFunctionIsNotDefined_thenConfigErrorIsRaised(self):
        act = lambda: partition_trigger.PartitionTrigger(partitionFunction=None)

        self.assertRaises(config.ConfigErrors, act)

    def test_runStep_whenPartitionFunctionReturnsNoBuilds_thenNoSchedulesIsTriggered(self):
        def yieldNoPartitions(buildStep, scheduler):
            if False:
                yield {'partition-index': -1}

        self.setupStep(partition_trigger.PartitionTrigger(partitionFunction=yieldNoPartitions, schedulerNames=['a'], sourceStamps = {}))

        self.expectOutcome(result=SUCCESS, status_text=['Zero partitions returned, nothing has been triggered'])
        return self.runStep()

    def test_runStep_whenPartitionYieldsBuilds_thenSchedulerIsTriggeredForEachBuild(self):
        def yieldPartitions(buildStep, scheduler):
            yield {'partition-index': 0}
            yield {'partition-index': 1}
            yield {'partition-index': 2}

        self.setupStep(partition_trigger.PartitionTrigger(partitionFunction=yieldPartitions, schedulerNames=['a'], sourceStamps = {}))

        self.expectOutcome(result=SUCCESS, status_text="Triggered: 'a' (split into 3 paritions)")
        self.aExpectTriggeredWith([
            ({}, {'partition-index': (0, 'PartitionTrigger'), 'stepname': ('PartitionTrigger', 'Trigger')}, 1),
            ({}, {'partition-index': (1, 'PartitionTrigger'), 'stepname': ('PartitionTrigger', 'Trigger')}, 1),
            ({}, {'partition-index': (2, 'PartitionTrigger'), 'stepname': ('PartitionTrigger', 'Trigger')}, 1)
        ])
        return self.runStep()

    def test_runStep_whenTriggerWithMultipleSchedulersPartitionYieldsBuilds_thenSchedulerIsTriggeredSchedulerAndForEachBuild(self):
        def yieldPartitions(buildStep, scheduler):
            if (scheduler.name == 'a'):
                yield {'partition-index': 0}
                yield {'partition-index': 1}
                yield {'partition-index': 2}
            elif (scheduler.name == 'b'):
                yield {'partition-index': 0, 'foo': 'bar'}
                yield {'partition-index': 1, 'foo': 'baz'}

        self.setupStep(partition_trigger.PartitionTrigger(partitionFunction=yieldPartitions, schedulerNames=['a', 'b'], sourceStamps = {}))

        self.expectOutcome(result=SUCCESS, status_text="Triggered: 'a' (split into 3 paritions)")
        self.aExpectTriggeredWith([
            ({}, {'partition-index': (0, 'PartitionTrigger'), 'stepname': ('PartitionTrigger', 'Trigger')}, 1),
            ({}, {'partition-index': (1, 'PartitionTrigger'), 'stepname': ('PartitionTrigger', 'Trigger')}, 1),
            ({}, {'partition-index': (2, 'PartitionTrigger'), 'stepname': ('PartitionTrigger', 'Trigger')}, 1)
        ])
        self.bExpectTriggeredWith([
            ({}, {'partition-index': (0, 'PartitionTrigger'), 'foo': ('bar', 'PartitionTrigger'), 'stepname': ('PartitionTrigger', 'Trigger')}, 1),
            ({}, {'partition-index': (1, 'PartitionTrigger'), 'foo': ('baz', 'PartitionTrigger'), 'stepname': ('PartitionTrigger', 'Trigger')}, 1)
        ])
        return self.runStep()
