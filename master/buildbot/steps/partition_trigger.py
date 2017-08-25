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

from buildbot import config
from buildbot.process.buildstep import LoggingBuildStep
from buildbot.steps.trigger import Trigger
from buildbot.process.properties import Properties

class PartitionTrigger(Trigger):
    name = "PartitionTrigger"

    # Same arguments as the Trigger but also a partition function that determines how many times each build should be
    # triggered scheduler should be triggered.
    def __init__(self, partitionFunction, **kwargs):
        if not partitionFunction:
            config.error("You must specify a parition function for the partition trigger")
        self.partitionFunction = partitionFunction

        Trigger.__init__(self, **kwargs)

    def _triggerSchedulers(self, triggered_schedulers):
        dl = []
        triggeredNames = []
        triggeredByBuildRequestId = self._triggeredByBuildRequestId()
        sourceStampForTrigger = self.prepareSourcestampListForTrigger()

        for sch in triggered_schedulers:
            partitions = self.partitionFunction(self, sch)
            partitionCount = 0
            for partition in partitions:
                propertiesToSetForPartition = self._createPartitionTriggerProperties(partition)
                dl.append(sch.trigger(sourceStampForTrigger, set_props=propertiesToSetForPartition,
                    triggeredbybrid=triggeredByBuildRequestId, reason=self.build.build_status.getReason()))
                partitionCount += 1
            if partitionCount == 0: # No partition triggered, so trigger the scheduler normally
                propertiesToSet = self.createTriggerProperties()
                dl.append(sch.trigger(sourceStampForTrigger, set_props=propertiesToSet,
                    triggeredbybrid=triggeredByBuildRequestId, reason=self.build.build_status.getReason()))
                triggeredNames.append("'%s'" % sch.name)
            else:
                triggeredNames.append("'%s' (split into %d partitions)" % (sch.name, partitionCount))

        self.step_status.setText(['Triggered:'] + triggeredNames)

        return dl

    def _createPartitionTriggerProperties(self, partitionProperties):
        propertiesToSetForPartition = self.createTriggerProperties()
        for key, value in partitionProperties.iteritems():
            propertiesToSetForPartition.setProperty(key, value, "PartitionTrigger")
        return propertiesToSetForPartition

    def createTriggerProperties(self):
        # make a new properties object from a dict rendered by the old
        # properties object
        trigger_properties = Properties()
        trigger_properties.update(self.set_properties, "Trigger")
        return trigger_properties

    def finished(self, results):
        from buildbot.status.results import SUCCESS, RESUME, DEPENDENCY_FAILURE, SKIPPED
        shouldResumeBuild = results == SUCCESS or results == SKIPPED or results == DEPENDENCY_FAILURE
        if shouldResumeBuild:
            text = ["Build Will Be Resumed"]
            self.step_status.stepFinished(results)
            self.build.buildFinished(text, RESUME)
        LoggingBuildStep.finished(self, results)
