
"""Definitions for datatypes used in configuration extensions."""

__all__ = ['ApplicationDataPath', 'DefaultPath', 'SoundFile', 'CustomSoundFile', 'HTTPURL', 'FileURL', 'AuthorizationToken', 'InvalidToken',
           'IconDescriptor', 'PresenceState', 'PresenceStateList', 'GraphTimeScale']

import os
import re

from urllib import pathname2url, url2pathname
from urlparse import urlparse

from application.python.types import MarkerType
from sipsimple.configuration.datatypes import Hostname, List

from blink.resources import ApplicationData


class ApplicationDataPath(unicode):
    def __new__(cls, path):
        path = os.path.normpath(path)
        if path.startswith(ApplicationData.directory+os.path.sep):
            path = path[len(ApplicationData.directory+os.path.sep):]
        return unicode.__new__(cls, path)

    @property
    def normalized(self):
        return ApplicationData.get(self)


class SoundFile(object):
    def __init__(self, path, volume=100):
        self.path = path
        self.volume = int(volume)
        if not (0 <= self.volume <= 100):
            raise ValueError('illegal volume level: %d' % self.volume)

    def __getstate__(self):
        return u'%s,%s' % (self.__dict__['path'], self.volume)

    def __setstate__(self, state):
        try:
            path, volume = state.rsplit(u',', 1)
        except ValueError:
            self.__init__(state)
        else:
            self.__init__(path, volume)

    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__, self.path, self.volume)

    def _get_path(self):
        return ApplicationData.get(self.__dict__['path'])
    def _set_path(self, path):
        path = os.path.normpath(path)
        if path.startswith(ApplicationData.directory+os.path.sep):
            path = path[len(ApplicationData.directory+os.path.sep):]
        self.__dict__['path'] = path
    path = property(_get_path, _set_path)
    del _get_path, _set_path


class DefaultPath: __metaclass__ = MarkerType

class CustomSoundFile(object): # check if this data type is still needed -Dan
    def __init__(self, path=DefaultPath, volume=100):
        self.path = path
        self.volume = int(volume)
        if not (0 <= self.volume <= 100):
            raise ValueError('illegal volume level: %d' % self.volume)

    def __getstate__(self):
        if self.path is DefaultPath:
            return u'default'
        else:
            return u'file:%s,%s' % (self.__dict__['path'], self.volume)

    def __setstate__(self, state):
        match = re.match(r'^(?P<type>default|file:)(?P<path>.+?)?(,(?P<volume>\d+))?$', state)
        if match is None:
            raise ValueError('illegal value: %r' % state)
        data = match.groupdict()
        if data.pop('type') == 'default':
            data['path'] = DefaultPath
        data['volume'] = data['volume'] or 100
        self.__init__(**data)

    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__, self.path, self.volume)

    def _get_path(self):
        path = self.__dict__['path']
        return path if path is DefaultPath else ApplicationData.get(path)
    def _set_path(self, path):
        if path is not DefaultPath:
            path = os.path.normpath(path)
            if path.startswith(ApplicationData.directory+os.path.sep):
                path = path[len(ApplicationData.directory+os.path.sep):]
        self.__dict__['path'] = path
    path = property(_get_path, _set_path)
    del _get_path, _set_path


class HTTPURL(unicode):
    def __new__(cls, value):
        value = unicode(value)
        url = urlparse(value)
        if url.scheme not in (u'http', u'https'):
            raise ValueError("illegal HTTP URL scheme (http and https only): %s" % url.scheme)
        Hostname(url.hostname)
        if url.port is not None and not (0 < url.port < 65536):
            raise ValueError("illegal port value: %d" % url.port)
        return value


class AuthorizationTokenMeta(type):
    def __init__(cls, name, bases, dic):
        super(AuthorizationTokenMeta, cls).__init__(name, bases, dic)
        cls._instances = {}
    def __call__(cls, *args):
        if len(args) > 1:
            raise TypeError('%s() takes at most 1 argument (%d given)' % (cls.__name__, len(args)))
        key = args[0] if args else ''
        if key not in cls._instances:
            cls._instances[key] = super(AuthorizationTokenMeta, cls).__call__(*args)
        return cls._instances[key]

class AuthorizationToken(str):
    __metaclass__ = AuthorizationTokenMeta
    def __repr__(self):
        if self is InvalidToken:
            return 'InvalidToken'
        else:
            return '%s(%s)' % (self.__class__.__name__, str.__repr__(self))

InvalidToken = AuthorizationToken() # a valid token is never empty


class FileURL(unicode):
    def __new__(cls, value):
        if not value.startswith('file:'):
            value = 'file:' + pathname2url(os.path.abspath(value).encode('utf-8')).decode('utf-8')
        return unicode.__new__(cls, value)


class ParsedURL(unicode):
    fragment = property(lambda self: self.__parsed__.fragment)
    netloc   = property(lambda self: self.__parsed__.netloc)
    params   = property(lambda self: self.__parsed__.params)
    path     = property(lambda self: self.__parsed__.path if self.scheme != 'file' else url2pathname(self.__parsed__.path))
    query    = property(lambda self: self.__parsed__.query)
    scheme   = property(lambda self: self.__parsed__.scheme)

    def __init__(self, value):
        self.__parsed__ = urlparse(self)


class IconDescriptor(object):
    def __init__(self, url, etag=None):
        self.url = ParsedURL(url)
        self.etag = etag

    def __getstate__(self):
        if self.etag is None:
            return unicode(self.url)
        else:
            return u'%s,%s' % (self.url, self.etag)

    def __setstate__(self, state):
        try:
            url, etag = state.rsplit(u',', 1)
        except ValueError:
            self.__init__(state)
        else:
            self.__init__(url, etag)

    def __eq__(self, other):
        if isinstance(other, IconDescriptor):
            return self.url == other.url and self.etag == other.etag
        return NotImplemented

    def __ne__(self, other):
        equal = self.__eq__(other)
        return NotImplemented if equal is NotImplemented else not equal

    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__, self.url, self.etag)


class PresenceState(object):
    def __init__(self, state, note=None):
        self.state = unicode(state)
        self.note = note

    def __getstate__(self):
        if not self.note:
            return unicode(self.state)
        else:
            return u'%s,%s' % (self.state, self.note)

    def __setstate__(self, data):
        try:
            state, note = data.split(u',', 1)
        except ValueError:
            self.__init__(data)
        else:
            self.__init__(state, note)

    def __eq__(self, other):
        if isinstance(other, PresenceState):
            return self.state == other.state and self.note == other.note
        return NotImplemented

    def __ne__(self, other):
        equal = self.__eq__(other)
        return NotImplemented if equal is NotImplemented else not equal

    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__, self.state, self.note)


class PresenceStateList(List):
    type = PresenceState


class GraphTimeScale(int):
    min_value = 2
    max_value = 4

    def __new__(cls, value):
        value = int(value)
        if not (cls.min_value <= value <= cls.max_value):
            raise ValueError("expected an integer number between %d and %d, found %d" % (cls.min_value, cls.max_value, value))
        return value


