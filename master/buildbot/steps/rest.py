from buildbot.steps.shell import ShellCommand
from buildbot.process.buildstep import SUCCESS
import json


class RestRequest(ShellCommand):
    name = "Rest Api Request"
    description="Invoking Web Api Request..."
    descriptionDone="Rest Api Request complete."

    def __init__(self, url, method, bodyFile, **kwargs):
        self.url = url
        self.method = method
        self.bodyFile = bodyFile
        self.master = None

        ShellCommand.__init__(self, collectStdout=True, collectStderr=True, **kwargs)

    def start(self):
        if self.master is None:
            self.master = self.build.builder.botmaster.parent

        if self._isWindowsSlave():
            command = self._createPowershellCommand(self.method, self.url, self.bodyFile)
        else:
            command = self._createShellCommand(self.method, self.url, self.bodyFile)

        self.setCommand(command)
        ShellCommand.start(self)


    def finished(self, results):
        # TODO: prefix property with stepname? self.name
        if results == SUCCESS:
            restresponse = json.loads(self.cmd.stdout)
            self.build.setProperty("rest-response", restresponse, self.name)
            self.build.setProperty("rest-response-headers", self.cmd.stderr, self.name)
        ShellCommand.finished(self, results)


    def _createShellCommand(self, method, url, in_file, contentType = "application/json", accept = "application/json"):
        return "curl -f -v -s -H 'Content-Type: %s' -H 'Accept: %s' -X %s --data-binary '@%s' %s" % (contentType, accept, method, in_file, url)


    # TODO: Figure out how to redirect body to stdout and headers to stderr
    def _createPowershellCommand(self, method, url, in_file, contentType = "application/json", accept = "application/json"):
        return ("powershell.exe -C "
            "$headers = New-Object 'System.Collections.Generic.Dictionary[[String],[String]]';"
            "$headers.Add('Accept', '%s');"
            "Invoke-RestMethod -ContentType %s -Headers $headers -InFile %s -Method %s -Uri %s;" % (accept, contentType, in_file, method, url))


    def _isWindowsSlave(self):
        slave_os = self.build.slavebuilder.slave.os and self.build.slavebuilder.slave.os == 'Windows'
        slave_env = self._checkWindowsSlaveEnvironment('os') or self._checkWindowsSlaveEnvironment('OS')
        return slave_os or slave_env


    def _checkWindowsSlaveEnvironment(self, key):
        return key in self.build.slavebuilder.slave.slave_environ.keys() \
            and self.build.slavebuilder.slave.slave_environ[key] == 'Windows_NT'
