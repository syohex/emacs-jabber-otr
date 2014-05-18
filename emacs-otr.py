#!/usr/bin/env python
#
# Copyright (C) 2014  Magnus Henoch <magnus.henoch@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

###
# This program is a thin interface to python-potr, a library for
# Off-The Record messaging written entirely in Python, which can be
# found at <https://github.com/python-otr/pure-python-otr>.  While it
# was written to provide OTR functionality for Emacs, it is not
# specific to Emacs and may be useful in other environments as well.
#
# The program reads a request from standard input, and writes a
# response to standard output.  Requests and responses are JSON
# values, preceded by a byte count on a line by itself.

import potr
import json
import sys

POLICY = {
    'ALLOW_V1':False,
    'ALLOW_V2':True,
    'REQUIRE_ENCRYPTION':True
}

# One size fits all:
MAX_MESSAGE_SIZE = 1024

class EmacsContext(potr.context.Context):
    def __init__(self, account, peername):
        super(EmacsContext, self).__init__(account, peername)

    def getPolicy(self, key):
        if key in POLICY:
            return POLICY[key]
        else:
            return False

    def inject(self, msg, appdata = None):
        inject_function = appdata
        inject_function(msg)

class EmacsAccount(potr.context.Account):
    contextclass = EmacsContext
    def __init__(self, name, directory, privkey=None):
        # protocol is unused?
        protocol = ''
        super(EmacsAccount, self).__init__(name, protocol, MAX_MESSAGE_SIZE, privkey)
        self.name = name
        self.contexts = {}
        self.directory = directory

    def get_context(self, contact):
        if contact in self.contexts:
            return self.contexts[contact]
        else:
            context = EmacsContext(self, contact)
            self.contexts[contact] = context
            return context

    def loadPrivkey(self):
        # TODO: what's the right way to expand a file name?
        privkey_file = self.directory + '/' + self.name + '.privkey'
        try:
            f = open(privkey_file, 'rb')
            key = f.read()
            f.close()
            return potr.compatcrypto.PK.parsePrivateKey(key)[0]
        except IOError:
            return None

    def savePrivkey(self):
        privkey_file = self.directory + '/' + self.name + '.privkey'
        #print "Writing %s to %s" % (self.privkey, privkey_file)
        f = open(privkey_file, 'wb')
        f.write(self.privkey.serializePrivateKey())
        f.close()

class EmacsOtr:
    def __init__(self, directory):
        self.accounts = {}
        self.directory = directory

    def get_account(self, name):
        if name in self.accounts:
            return self.accounts[name]
        else:
            # TODO: do something clever with privkey
            account = EmacsAccount(name, self.directory)
            self.accounts[name] = account
            return account

    def handle_command(self, cmd):
        which = cmd['command']
        injected = []
        def inject(msg):
            injected.append(msg)

        if which == 'receive':
            account_name = cmd['account']
            contact = cmd['contact']
            body = cmd['body']
            closure = cmd.get('closure', None)

            account = self.get_account(account_name)
            context = account.get_context(contact)

            result = context.receiveMessage(body, inject)
            return {'result': result, 'injected': injected, 'closure': closure}
        elif which == 'send':
            account_name = cmd['account']
            contact = cmd['contact']
            body = cmd['body']
            closure = cmd.get('closure', None)

            account = self.get_account(account_name)
            context = account.get_context(contact)

            result = context.sendMessage(potr.context.FRAGMENT_SEND_ALL,
                                         body,
                                         appdata = inject)
            return {'result': result, 'injected': injected, 'closure': closure}
        else:
            return {'error': 'Unknown commmand "%s"' % which}

directory = sys.argv[1]
otr = EmacsOtr(directory)

while True:
    # Read a number, followed by newline...
    nbytes = int(input())
    #print "read length %d" % nbytes
    # ...which tells us how many bytes to read.
    data = sys.stdin.read(nbytes)
    #print "read data: %s" % data
    decoded = json.loads(data)
    result = otr.handle_command(decoded)
    encoded = json.dumps(result)
    # Likewise when returning the result:
    sys.stdout.write("%d\n%s" % (len(encoded), encoded))
