#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pylint: disable=C0103
# pylint: disable=W0702
# pylint: disable=R0912
# pylint: disable=R0915
# pylint: disable=R0914

"""Arsenic development

This is WIP code under active development.

"""
import ConfigParser
import StringIO
import anydbm
import cProfile
import imp
import os
import platform
import pstats
import sqlite3
import sys
import time
import urllib2

import dill as pickle
from twisted.internet import protocol, reactor, ssl
from twisted.python import log
from twisted.words.protocols import irc

import encoder  # Local module, can be overridden with mod_load

pr = cProfile.Profile()


class conf(Exception):
    """Automatically generated"""


VER = '1.4.0b3'

try:
    if sys.argv[1].startswith('--config='):
        config_dir = sys.argv[1].split('=', 1)[1]
        if config_dir == '':
            raise conf('No path specified')
        else:
            if not os.path.isdir(config_dir):
                raise conf('config path not found')
except:
    raise conf(
        'arsenic takes a single argument, --config=/path/to/config/dir')

cfile = open(os.path.join(config_dir, 'kgb.conf'), 'r+b')
config = ConfigParser.ConfigParser()
config.readfp(cfile)


def config_save():
    cfile.seek(0)  # This mess is required
    cfile.truncate()  # otherwise we get in to this weird
    cfile.flush()  # situation where we have 2
    config.write(cfile)  # configs in one file
    cfile.flush()


def config_get(module, item, default=False):
    if config.has_option(module, item):
        return config.get(module, item)
    else:
        return default


def config_set(module, item, value):
    if not config.has_section(module):
        config.add_section(module)

    config.set(module, item, value)
    config_save()
    return True


def config_remove(module, item):
    if config.has_section(module) and config.has_option(module, item):
        config.remove_option(module, item)
        config_save()
        return True

    else:
        return False


try:
    hostname = config.get('network', 'hostname')
except:
    raise conf('Unable to read hostname')

try:
    port = config.getint('network', 'port')
except:
    raise conf('Unable to read port')

try:
    oplist = set(config.get('main', 'op').replace(' ', '').split(','))
    for user in oplist:
        if user.startswith('!'):
            oplist.remove(user)
            oplist.add(encoder.decode(user))

except:
    print 'Unable to read ops, assuming none'
    oplist = []

ownerlist = oplist

modlook = {}
try:
    modules = config.get('main', 'mod').replace(' ', '').split(',')
except:
    print 'Unable to read modules, assuming none'
    modules = []

# relays messages without a log
try:
    debug = config.getboolean('main', 'debug')
except:
    debug = False
    log.msg('Debug unset, defaulting to off')

try:
    updateconfig = config.getboolean('main', 'updateconfig')
except:
    updateconfig = False

if not updateconfig:
    cfile.close()  # Close this if we don't need it later

if debug:
    file_log = 'stdout'
    log.startLogging(sys.stdout)
else:
    file_log = 'kgb-' + time.strftime("%Y_%m_%d-%H%M%S") + '.log'
    log.startLogging(open(file_log, 'w'))

log.msg("KittyHawk %s, log: %s" % (VER, file_log))

mod_declare_privmsg = {}
mod_declare_userjoin = {}
mod_declare_syncmsg = {}

channel_user = {}

sync_channels = {}

try:
    for lists in config.get('main', 'sync_channel').split(','):
        items = lists.split('>')
        sync_channels[items[0]] = items[1]

except:
    pass

try:  # ^help/etc
    key = config.get('main', 'command_key').replace('', '^')
except:
    key = '^'

irc_relay = ""

isconnected = False

try:
    irc_relay = config.get('main', 'log')
except:
    log.msg("no relay log channel")

db_name = ""

try:
    db_name = os.path.join(config_dir, config.get('main', 'db'))
except:
    db_name = ""

try:
    cache_name = config.get('main', 'cache')
except:
    cache_name = ".cache"

cache_name = os.path.join(config_dir, cache_name)

cache_state = 1

print "Using cache: " + cache_name
cache_fd = anydbm.open(cache_name, 'c')

print cache_fd

if os.path.isfile(db_name) is False:
    log.err("No database found!")
    raise SystemExit(0)


class Profile:
    def __init__(self, connector):
        self.connector = connector

    def register(self, usermask):

        nick = usermask.split('!', 1)[0]
        ident = usermask.split('!', 1)[1].split('@', 1)[0]
        hostmask = usermask.split('@', 1)[1]

        self.connector.execute('insert into profile(nickname, ident, hostmask) values (?, ?, ?)',
                               (nick, ident, hostmask,))
        self.connector.commit()

        print ("Created user %s" % nick)

        return user

    def getuser(self, usermask):
        global unit
        print "THIS SHOULD ALWAYS SEND"

        nick = usermask.split('!', 1)[0]
        ident = usermask.split('!', 1)[1].split('@', 1)[0]
        hostmask = usermask.split('@', 1)[1]

        try:
            c = self.connector.execute('select * from profile where hostmask = ?',
                                       (hostmask,))  # This is fucking broken gonna kmsa

            if c is None:
                c = self.connector.execute('select * from profile where nickname = ? and ident = ?', (nick, ident,))

                if c is None:
                    print "No user!"

                else:
                    u = c.fetchone()
                    self.connector.execute('update profile set hostname = ? where nickname = ?', (hostmask, nickname,))
                    self.connector.commit()

        except:
            print "ERR"
            return False


        else:
            u = c.fetchone()

        username = u[0]

        loc_lat = u[3]
        loc_lng = u[4]

        if u[5] is None:
            unit = 'auto'
        elif u[5] == 0:
            unit = 'us'
        elif u[5] == 1:
            unit = 'si'
        elif u[5] == 2:
            unit = 'ca'
        elif u[5] == 3:
            unit = 'uk2'

        if u[6] == 0:
            gender = False
        elif u[6] == 1:
            gender = True
        else:
            gender = None

        height = u[7]  # cm
        weight = u[8]  # kg

        if u[9] == 1:
            privacy = True
        else:
            privacy = False

        if u[10] == 1:
            isverified = True
        else:
            isverified = False

        if u[11] == 1:
            isop = True
        else:
            isop = False

        class user:
            def __init__(self):
                pass

        setattr(user, 'username', username)
        setattr(user, 'nickname', nick)
        setattr(user, 'ident', ident)
        setattr(user, 'hostname', hostname)
        setattr(user, 'lat', loc_lat)
        setattr(user, 'lng', loc_lng)
        setattr(user, 'unit', unit)
        setattr(user, 'gender', gender)
        setattr(user, 'height', height)
        setattr(user, 'weight', weight)
        setattr(user, 'privacy', privacy)
        setattr(user, 'isverified', isverified)
        setattr(user, 'isop', isop)

        return user


def save():
    clist = ''
    slist = ''

    for i in channel_list:
        clist = '%s, %s' % (clist, i)

    if clist[0] != '#':
        clist = clist[2:]

    try:  # silent catched error if not syncing
        for i in sync_channels:
            slist = '%s,%s>%s' % (slist, i, sync_channels[i])

        if slist[0] != '#':
            slist = slist[1:]

        print slist
        config.set('main', 'sync_channel', slist)

    except:
        pass

    config.set('main', 'channel', clist)
    config_save()


def checkauth(user):
    """Checks if hostmask is bot op"""

    user_host = user.split('!', 1)[1]

    try:  # needed for non message op commands
        c = conn.execute(
            'SELECT * FROM op WHERE username = ?', (user_host,))
    except:
        c = None

    if c is not None:

        # for user in oplist:    #disabled as this is a major DoS
        #    if user.startswith('!'):
        #        oplist.remove(user)
        #        oplist.add(encoder.decode(user))

        if user_host in oplist:
            return True

        elif c.fetchone() is not None:
            return True

        else:
            return False

    else:
        if user_host in oplist:
            return True

        else:
            return False


def checkowner(user):
    """Checks if hostmask is bot owner"""

    user_host = user.split('!', 1)[1]

    if user_host in ownerlist:
        return True
    else:
        return False


class Arsenic(irc.IRCClient):
    """Twisted callbacks registered here"""

    def __init__(self, profileManager, extra=False):
        self.profileManager = profileManager
        self.__extra__ = extra
        if extra:
            self.msg = extra.msg

        return

    class persist:
        def __init__(self):
            pass

    save = persist()

    lockerbox = {}

    floodprotect = False

    versionName = 'KittyHawk'
    versionNum = VER
    versionEnv = platform.system()
    sourceURL = "https://github.com/KittyHawkIRC"

    nickname = config.get('main', 'name')

    # Joins channels on invite
    autoinvite = config.getboolean('main', 'autoinvite')

    def join(self, channel):  # hijack superclass join
        if not channel in channel_list:
            channel_list.append(channel)
            if updateconfig:  # Save file every join call
                save()
        irc.IRCClient.join(self, channel)

    def leave(self, channel):  # hijacks superclass leave
        if channel in channel_list:
            channel_list.remove(channel)
            if updateconfig:  # Save file every leave call
                save()
        irc.IRCClient.leave(self, channel)

    def cache_save(self):

        for item in self.lockerbox:
            log.msg("Saving:" + item)
            log.msg("data: " + str(pickle.dumps(self.lockerbox[item])))
            cache_fd[item] = pickle.dumps(self.lockerbox[item])
            log.msg("Validating: " + str(cache_fd[item]))

        print log.msg(str(cache_fd))

    def cache_load(self):
        # In theory, this should work

        for item in cache_fd.keys():

            try:
                self.lockerbox[item] = pickle.loads(cache_fd[item])
            except:
                log.msg("Error loading cache: " + item)

    def cache_status(self):
        if cache_state == 1:
            self.msg(self.channel, 'Cache loaded correctly (%s)' % cache_name)
        elif cache_state == 2:
            self.msg(self.channel, 'Cache loaded read only (%s)' % cache_name)
        elif cache_state == 3:
            self.msg(self.channel, 'A new cache was created (%s)' % cache_name)
        elif cache_state == 0:
            self.msg(self.channel, 'Unable to load cache entirely (%s)' % cache_name)

    def connectionMade(self):
        irc.IRCClient.connectionMade(self)
        self.msg('NickServ', 'identify ' + self.factory.nspassword)

    def connectionLost(self, reason):
        irc.IRCClient.connectionLost(self, reason)

    # callbacks for events
    def signedOn(self):
        try:  # silent error if no nickname
            nickname = config.get('main', 'nickname')
            self.nickname = nickname
            self.setNick(nickname)

        except:
            pass

        for i in channel_list:
            channel_user[i.lower()] = [self.nickname]
            self.join(i)

        self.cache_load()  # load cached lockerbox

    def kickedFrom(self, channel, user, message):
        time.sleep(3)
        self.join(channel)
        del user

    def syncmsg(self, cbuser, inchannel, outchannel, msg):
        setattr(self, 'type', 'syncmsg')
        setattr(self, 'message', msg)
        setattr(self, 'user', cbuser)
        setattr(self, 'incoming_channel', inchannel)
        setattr(self, 'outgoing_channel', outchannel)
        setattr(self, 'ver', VER)
        setattr(self, 'store', save)

        ##### Hijack config object functions to reduce scope

        def __config_get__(item, default=False):  # stubs, basically
            return config_get(mod_declare_privmsg[command], item, default)

        def __config_set__(item, value):
            return config_set(mod_declare_privmsg[command], item, value)

        def __config_remove__(item):
            return config_remove(mod_declare_privmsg[command], item)

        setattr(self, 'config_get', __config_get__)
        setattr(self, 'config_set', __config_set__)
        setattr(self, 'config_remove', __config_remove__)

        for command in mod_declare_syncmsg:
            try:
                self.lockerbox[command]
            except:
                self.lockerbox[command] = self.persist()
            setattr(self, 'locker', self.lockerbox[command])

            modlook[
                mod_declare_syncmsg[command]].callback(
                self)

    def userJoined(self, cbuser, cbchannel):
        setattr(self, 'type', 'userjoin')
        setattr(self, 'user', cbuser)
        setattr(self, 'channel', cbchannel)
        setattr(self, 'ver', VER)

        ##### Hijack config object functions to reduce scope

        for command in mod_declare_userjoin:
            modlook[
                mod_declare_userjoin[command]].callback(
                self)

    def privmsg(self, user, channel, msg):

        try:  # I forgot why this exists but it causes bugs
            pass
            # user = user.split(key, 1)[0]
        except:
            user = user

        if user == self.nickname:
            return

            if not channel.startswith('#'):
                channel = user.split('!')

        auth = checkauth(user)
        owner = checkowner(user)

        # Start module execution

        command = msg.split(' ', 1)[0].lower()

        lower_channel = channel.lower()
        if lower_channel in sync_channels:  # syncing
            u = user.split('!', 1)[0]
            self.msg(sync_channels[lower_channel], '<%s> %s' % (u, msg))
            self.syncmsg(user, lower_channel,
                         sync_channels[lower_channel], msg)
        self.cache_save()

        iskey = False

        if command.startswith(key):
            command = command.split(key, 1)[1]
            iskey = True
        else:
            command = command

        if iskey or (channel == self.nickname and auth):

            setattr(self, 'isop', auth)
            setattr(self, 'isowner', owner)
            setattr(self, 'type', 'privmsg')
            setattr(self, 'command', command)
            setattr(self, 'message', msg)
            setattr(self, 'user', user)
            setattr(self, 'channel', channel)
            setattr(self, 'ver', VER)

            if command in mod_declare_privmsg:
                try:
                    self.lockerbox[mod_declare_privmsg[command]]
                except:
                    self.lockerbox[mod_declare_privmsg[
                        command]] = self.persist()

                self.cache_save()

                # attributes
                setattr(self, 'store', save)
                setattr(self, 'locker', self.lockerbox[
                    mod_declare_privmsg[command]])

                ##### Hijack config object functions to reduce scope

                def __config_get__(item, default=False):  # stubs, basically
                    return config_get(mod_declare_privmsg[command], item, default)

                def __config_set__(item, value):
                    return config_set(mod_declare_privmsg[command], item, value)

                def __config_remove__(item):
                    return config_remove(mod_declare_privmsg[command], item)

                setattr(self, 'config_get', __config_get__)
                setattr(self, 'config_set', __config_set__)
                setattr(self, 'config_remove', __config_remove__)

            log_data = "Command: %s, user: %s, channel: %s, data: %s" % (
                command, user, channel, msg)
            log.msg(log_data)

            u = user.split('!', 1)[0]

            if channel == self.nickname:
                # private commands

                if irc_relay != "":
                    self.msg(irc_relay, user + " said " + msg)

                if owner:
                    if msg.startswith('op'):

                        host = msg.split(' ', 1)[1]
                        extname = host.split('!', 1)[0]
                        c = conn.execute('INSERT INTO op(username) VALUES (?)',
                                         (host.split('!', 1)[1],))
                        conn.commit()

                        self.msg(
                            user.split(
                                '!',
                                1)[0],
                            'Added user %s to the op list' %
                            extname)
                        self.msg(extname, "You've been added to my op list")

                    elif msg.startswith('deop'):

                        host = msg.split(' ', 1)[1]
                        extname = host.split('!', 1)[0]
                        c = conn.execute('DELETE FROM op WHERE username = ?',
                                         (host.split('!', 1)[1],))
                        conn.commit()

                        self.msg(
                            user.split(
                                '!',
                                1)[0],
                            'Removed user %s from the op list' %
                            extname)

                    elif msg.startswith('prof_on'):
                        pr.enable()
                        self.msg(u, 'profiling on')

                    elif msg.startswith('prof_off'):
                        pr.disable()
                        self.msg(u, 'profiling off')

                    elif msg.startswith('prof_stat'):
                        s = StringIO.StringIO()
                        sortby = 'cumulative'
                        ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
                        ps.print_stats()
                        self.msg(u, s.getvalue())

                    elif msg.startswith('mod_inject'):
                        mod = msg.split(' ')[1]
                        url = msg.split(' ')[2]
                        req = urllib2.Request(
                            url, headers={'User-Agent': 'UNIX:KittyHawk http://github.com/KittyHawkIRC'})

                        fd = urllib2.urlopen(req)
                        mod_src = open(
                            config_dir + '/modules/' + mod + '.py', 'w')

                        data = fd.read()
                        mod_src.write(data)
                        os.fsync(mod_src)

                        fd.close()
                        mod_src.close()

                    elif msg.startswith('mod_load'):
                        mod = msg.split(' ')[1]

                        mod_src = open(config_dir + '/modules/' + mod + '.py')
                        mod_bytecode = compile(
                            mod_src.read(), '<string>', 'exec')
                        mod_src.close()

                        modlook[mod] = imp.new_module(mod)
                        sys.modules[mod] = modlook[mod]

                        exec mod_bytecode in modlook[mod].__dict__

                        declare_table = modlook[mod].declare()

                        for i in declare_table:
                            cmd_check = declare_table[i]

                            if cmd_check == 'privmsg':
                                mod_declare_privmsg[i] = mod

                            elif cmd_check == 'userjoin':
                                mod_declare_userjoin[i] = mod

                            elif cmd_check == 'syncmsg':
                                mod_declare_syncmsg[i] = mod

                    elif msg.startswith('update_inject'):
                        try:
                            url = msg.split(' ')[1]
                        except:
                            url = 'https://raw.githubusercontent.com/KittyHawkIRC/core/master/arsenic.py'
                        req = urllib2.Request(
                            url, headers={'User-Agent': 'UNIX:KittyHawk http://github.com/KittyHawkIRC'})

                        fd = urllib2.urlopen(req)
                        mod_src = open(sys.argv[0], 'w')

                        data = fd.read()
                        mod_src.write(data)
                        os.fsync(mod_src)

                        fd.close()
                        mod_src.close()

                    elif msg.startswith('update_restart'):
                        try:
                            mod_src = open(sys.argv[0])
                            compile(mod_src.read(), '<string>',
                                    'exec')  # syntax testing

                            args = sys.argv[:]
                            args.insert(0, sys.executable)
                            # os.chdir(_startup_cwd)
                            os.execv(sys.executable, args)
                        except:
                            self.msg(u, 'Syntax error!')

                    elif msg.startswith('update_patch'):
                        mod_src = open(sys.argv[0])
                        mod_bytecode = compile(
                            mod_src.read(), '<string>', 'exec')
                        mod_src.close()

                        update = imp.new_module('update')
                        exec mod_bytecode in update.__dict__

                        old = self
                        self.__class__ = update.Arsenic
                        self = update.Arsenic(old)

                        self.msg(u, 'Attempted runtime patching (%s)' % VER)

                    elif msg.startswith('inject'):
                        self.lineReceived(msg.split(' ', 1)[1])

                    elif msg.startswith('raw'):
                        self.sendLine(msg.split(' ', 1)[1])

                    elif msg.startswith('config_get'):
                        opts = msg.split()
                        module = opts[1]
                        item = opts[2]
                        self.msg(u, str(config_get(module, item, False)))

                    elif msg.startswith('config_set'):
                        opts = msg.split()
                        module = opts[1]
                        item = opts[2]

                        value_list = opts[3:]
                        value = ''
                        for i in value_list:
                            value += i + ' '

                        self.msg(u, str(config_set(module, item, value[:len(value) - 1])))

                    elif msg.startswith('config_remove'):
                        opts = msg.split()
                        module = opts[1]
                        item = opts[2]
                        self.msg(u, str(config_remove(module, item)))

                    elif msg.startswith('config_list'):
                        opts = msg.split()
                        module = opts[1]
                        if config.has_section(module):
                            self.msg(u, str(config.options(module)))
                        else:
                            self.msg(u, 'no section for that module!')

                    elif msg == 'sync_list':
                        for i in sync_channels:
                            self.msg(u, '%s -> %s' % (i, sync_channels[i]))

                    elif msg.startswith('sync'):
                        ch1 = msg.split(' ')[1].lower()
                        ch2 = msg.split(' ')[2].lower()

                        if ch1 in sync_channels:
                            self.msg(u, 'WARNING: %s already syncs to %s, overridden' % (
                                ch1, sync_channels[ch1]))

                        sync_channels[ch1] = ch2

                        self.msg(u, '%s -> %s' % (ch1, ch2))

                    elif msg.startswith('unsync'):
                        ch1 = msg.split(' ')[1].lower()

                        if ch1 in sync_channels:
                            del sync_channels[ch1]
                            self.msg(u, '%s -> X' % ch1)
                        else:
                            self.msg(u, 'Channel not currently being synced')

                    elif msg.startswith('cache_save'):
                        self.cache_save()

                    elif msg.startswith('cache_load'):
                        self.cache_load()

                    elif msg.startswith('cache_status'):
                        self.cache_status()


                    elif msg.startswith('help_config'):
                        self.msg(u, 'KittyHawk Ver: %s' % VER)
                        self.msg(u, 'Config commands: (note: owner only)')
                        self.msg(u, 'config_set {module} {item} {value} (Sets a value for a module)')
                        self.msg(u, 'config_get {module} {item} (Returns a value)')
                        self.msg(u, 'config_remove {module} {item} (Removes a value)')
                        self.msg(u, 'config_list {module} (Lists all items for a module)')

                    elif msg.startswith('help_sysop'):
                        self.msg(u, 'KittyHawk Ver: %s' % VER)
                        self.msg(
                            u, "DO NOT USE THESE UNLESS YOU KNOW WHAT YOU'RE DOING")
                        self.msg(u, 'SysOP commands:')
                        self.msg(
                            u, 'op {hostmask}, deop {hostmask}  (add or remove a user)')
                        self.msg(
                            u, 'prof_on, prof_off (enable or disable profiling, DO NOT USE)')
                        self.msg(
                            u, 'restart, prof_stat (Restart or display profiling stats (see ^))')
                        self.msg(
                            u, 'mod_load {module}, mod_reload {module} (Load or reload a loaded module)')
                        self.msg(
                            u, 'mod_inject {module} {url} (Download a module over the internet. (is not loaded))')
                        self.msg(
                            u, 'raw {line}, inject {line} (raw sends a raw line, inject assumes we recieved a line)')
                        self.msg(
                            u, 'update_restart, update_patch (Updates by restarting or patching the runtime)')
                        self.msg(
                            u, 'update_inject {optional:url} Downloads latest copy over the internet, not updated')
                        self.msg(
                            u, 'sync {channel1} {channel2}, unsync {channel1}')
                        self.msg(u, 'sync_list, msg {channel} {message}')
                        self.msg(u, 'cache_save, cache_load, cache_status')

                if auth:
                    if msg.startswith('add'):

                        cmd = msg.split(' ', 2)[1].lower()
                        data = msg.split(' ', 2)[2]
                        conn.execute(
                            ('insert or replace into command(name, response) '
                             'values (?, ?)'), (cmd.decode('utf-8'), data.decode('utf-8')))
                        conn.commit()

                        if data.startswith('!'):
                            data = encoder.decode(data)
                        self.msg(
                            user.split(
                                '!', 1)[0], 'Added the command %s with value %s' %
                                            (cmd, data))

                    elif msg.startswith('del'):

                        cmd = msg.split(' ')[1].lower()

                        conn.execute('DELETE FROM command WHERE name = ?',
                                     (cmd.decode('utf-8'),))
                        conn.commit()

                        self.msg(
                            user.split(
                                '!',
                                1)[0],
                            'Removed command %s' %
                            cmd)

                    elif msg == 'help':
                        self.msg(u, 'KittyHawk Ver: %s' % VER)
                        self.msg(u, 'Howdy, %s, you silly operator.' % u)
                        self.msg(
                            u, 'You have access to the following commands:')
                        self.msg(u, 'add {command} {value}, del {command}')
                        self.msg(u, 'join {channel}, leave {channel}')
                        self.msg(u, 'nick {nickname}, topic {channel} {topic}')
                        self.msg(u, 'kick {channel} {name} {optional reason}')
                        self.msg(u, 'ban/unban {channel} {hostmask}')

                    elif msg.startswith('mod_update'):
                        mod = msg.split(' ')[1]

                        if not mod in modlook:
                            self.msg(u, 'Unknown module! (%s)' % mod)
                            return

                        try:
                            url = modlook[mod].__url__
                        except:
                            self.msg(u, 'Error, module lacks update schema')
                            return

                        try:
                            # Impersonate the first owner, yolo
                            op = 'fake!' + list(ownerlist)[0]
                        except Exception, err:
                            log.err(err)
                            self.msg(u, 'Error, no owners are defined')
                            return

                        inject = 'mod_inject %s %s' % (mod, url)
                        load = 'mod_load %s' % mod

                        try:
                            # It's dirty, but
                            self.privmsg(op, channel, inject)
                            self.privmsg(op, channel, load)  # this shit works
                            self.msg(u, 'Module updated')
                        except:
                            self.msg(u, 'an error occured updating the module')

                if command in mod_declare_privmsg:
                    modlook[
                        mod_declare_privmsg[
                            command]].callback(
                        self)

            elif msg.startswith(key):

                if command in mod_declare_privmsg:
                    modlook[
                        mod_declare_privmsg[
                            command]].callback(
                        self)

                    self.cache_save()

                elif msg.startswith(key + 'help'):

                    self.msg(
                        u, 'Howdy, %s, please visit https://commands.tox.im to view the commands.' % u)

                else:
                    c = conn.execute(
                        'SELECT response FROM command WHERE name == ?', (command.decode('utf-8'),))

                    r = c.fetchone()
                    if r is not None:
                        rs = str(r[0])
                        if rs.startswith('!'):
                            rs = encoder.decode(rs)

                        if self.floodprotect:  # adds a space every other command. ha
                            rs = rs + ' '
                            self.floodprotect = False
                        else:
                            self.floodprotect = True

                        try:
                            u = msg.split(' ')[1]
                            self.msg(channel, "%s: %s" % (u, rs))

                        except:
                            self.msg(channel, rs)

    def lineReceived(self, line):  # ACTUAL WORK
        # Twisted API emulation

        global isconnected

        data = ''
        channel = ''
        server = ''
        user = ''
        command = ''
        victim = ''

        raw_line = line
        # :coup_de_shitlord!~coup_de_s@fph.commiehunter.coup PRIVMSG #FatPeopleHate :the raw output is a bit odd though
        line = line.split(' ')

        # if True:
        try:
            if line[0].startswith(':'):  # 0 is user, so 1 is command
                user = line[0].split(':', 1)[1]
                command = line[1]

                if not command.isdigit():  # on connect we're spammed with commands that aren't valid

                    if line[2].startswith('#'):  # PRIVMSG or NOTICE in channel
                        channel = line[2]

                        if command == 'KICK':  # It's syntax is normalized for :
                            victim = line[3]
                            data = raw_line.split(' ', 4)[4].split(':', 1)[1]

                        elif command == 'MODE':
                            victim = line[4]
                            data = line[3]

                        elif command == 'PART':
                            if len(line) == 4:  # Implies part message
                                data = raw_line.split(
                                    ' ', 3)[3].split(':', 1)[1]
                            else:
                                data = ''

                        else:
                            if line[3] == ':ACTION':  # /me, act like normal message
                                data = raw_line.split(
                                    ' ', 4)[4].split(':', 1)[1]
                            else:
                                data = raw_line.split(
                                    ' ', 3)[3].split(':', 1)[1]

                    elif line[2].startswith(':#'):  # JOIN/KICK/ETC
                        channel = line[2].split(':', 1)[1]

                    else:  # PRIVMSG or NOTICE via query
                        channel = self.nickname

                        if line[2] == ':ACTION':  # /me, act like normal message
                            data = raw_line.split(' ', 3)[3].split(':', 1)[1]
                        else:
                            data = raw_line.split(' ', 2)[2].split(':', 1)[1]

            else:
                command = line[0]  # command involving server
                server = line[1].split(':', 1)[1]

            if not command.isdigit():

                if command == 'NOTICE' and 'connected' in data.lower() and isconnected == False:
                    # DIRTY FUCKING HACK
                    # 100% UNSAFE. DO NOT USE THIS IN PRODUCTION
                    # Proposed fixes: No idea,
                    # need to google things

                    self.connectionMade()
                    self.signedOn()
                    isconnected = True  # dirter hack, makes sure this only runs once

                if command == 'PING':
                    self.sendLine('PONG ' + server)

                elif command == 'PRIVMSG':  # privmsg(user, channel, msg)
                    self.privmsg(user, channel, data)

                elif command == 'JOIN':
                    user = user.split('!', 1)[0]
                    self.userJoined(user, channel)
                    channel_user[channel.lower()] = [user.strip('~%@+&')]

                elif command == 'PART':
                    user = user.split('!', 1)[0]

                    if channel.lower() in channel_user:
                        if user in channel_user[channel.lower()]:
                            channel_user[channel.lower()].remove(user)
                        else:
                            log.err(
                                "Warning: Tried to remove unknown user. (%s)" % user)

                    else:
                        log.err("Warning: Tried to remove user from unknown channel. (%s, %s)" % (
                            channel.lower(), user))

                elif command == 'QUIT':
                    user = user.split('!', 1)[0]

                    for i in channel_user:
                        if user in channel_user[i]:
                            channel_user[i].remove(user)

                elif command == 'NICK':
                    user = user.split('!', 1)[0]

                    if channel.lower() in channel_user:
                        if user in channel_user[channel.lower()]:
                            channel_user[channel.lower()].remove(user)
                        else:
                            log.err(
                                "Warning: Tried to remove unknown user. (%s)" % user)

                    else:
                        log.err("Warning: Tried to remove user from unknown channel. (%s, %s)" % (
                            channel.lower(), user))

                    channel_user[channel.lower()] = [data]

                elif command == 'KICK':
                    # checks if we got kicked
                    if victim.split('!')[0] == self.nickname:
                        self.kickedFrom(channel, victim, data)

                elif command == 'INVITE':
                    if self.autoinvite:
                        self.join(data)

            elif line[1] == '353':  # NAMES output
                if line[3].startswith('#'):
                    channel = line[3].lower()
                    raw_user = raw_line.split(' ', 4)[4].split(':', 1)[1]
                else:
                    channel = line[4].lower()
                    raw_user = raw_line.split(' ', 5)[5].split(':', 1)[1]

                if channel not in channel_user:
                    channel_user[channel] = [self.nickname]

                for i in raw_user.split(' '):

                    if i not in channel_user[channel]:
                        channel_user[channel].append(i.strip('~%@+&'))

        # else:
        except Exception as err:
            log.err("Exception: %s" % err)
            log.err("Error: %s, LN: %s" %
                    (raw_line, sys.exc_info()[-1].tb_lineno))


class ArsenicFactory(protocol.ClientFactory):
    """Main irc connector"""

    def __init__(self, conn, channel, username, nspassword):
        self.conn = conn
        self.channel = channel
        self.profileManager = Profile(conn)

        self.username = username
        self.nspassword = nspassword

    def buildProtocol(self, addr):
        p = Arsenic(self.profileManager)
        p.factory = self
        return p

    def clientConnectionLost(self, connector, reason):
        connector.connect()

    def clientConnectionFailed(self, connector, reason):
        log.err("connection failed: %s" % reason)
        reactor.stop()


if __name__ == '__main__':
    conn = sqlite3.connect(db_name)

    for mod in modules:
        mod_src = open(config_dir + '/modules/' + mod + '.py')
        mod_bytecode = compile(mod_src.read(), '<string>', 'exec')
        mod_src.close()

        modlook[mod] = imp.new_module(mod)
        sys.modules[mod] = modlook[mod]
        exec mod_bytecode in modlook[mod].__dict__

        declare_table = modlook[mod].declare()

        for i in declare_table:
            cmd_check = declare_table[i]

            if cmd_check == 'privmsg':
                mod_declare_privmsg[i] = mod

            elif cmd_check == 'userjoin':
                mod_declare_userjoin[i] = mod

            elif cmd_check == 'syncmsg':
                mod_declare_syncmsg[i] = mod

    try:
        channel_list = config.get(
            'main', 'channel').replace(' ', '').split(',')

        f = ArsenicFactory(conn, channel_list[0], config.get('main', 'name'),
                           config.get('main', 'password'))
    except IndexError:
        raise SystemExit(0)

    reactor.connectSSL(hostname, port, f, ssl.ClientContextFactory())

    reactor.run()
