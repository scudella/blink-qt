# Copyright (C) 2013 AG Projects. See LICENSE for details.
#

__all__ = ['HistoryManager']

import re
import cPickle as pickle

from application.notification import IObserver, NotificationCenter
from application.python import Null
from application.python.types import Singleton
from collections import deque
from datetime import date, datetime
from zope.interface import implements

from sipsimple.account import BonjourAccount
from sipsimple.addressbook import AddressbookManager
from sipsimple.threading import run_in_thread

from blink.resources import ApplicationData
from blink.util import run_in_gui_thread


class HistoryManager(object):
    __metaclass__ = Singleton
    implements(IObserver)

    def __init__(self):
        try:
            data = pickle.load(open(ApplicationData.get('calls_history')))
        except Exception:
            self.missed_calls = deque(maxlen=10)
            self.placed_calls = deque(maxlen=10)
            self.received_calls = deque(maxlen=10)
        else:
            self.missed_calls, self.placed_calls, self.received_calls = data
        notification_center = NotificationCenter()
        notification_center.add_observer(self, name='SIPSessionDidEnd')
        notification_center.add_observer(self, name='SIPSessionDidFail')

    @run_in_thread('file-io')
    def save(self):
        with open(ApplicationData.get('calls_history'), 'wb+') as f:
            pickle.dump((self.missed_calls, self.placed_calls, self.received_calls), f)

    @run_in_gui_thread
    def handle_notification(self, notification):
        handler = getattr(self, '_NH_%s' % notification.name, Null)
        handler(notification)

    def _NH_SIPSessionDidEnd(self, notification):
        if notification.sender.account is BonjourAccount():
            return
        session = notification.sender
        entry = HistoryEntry.from_session(session)
        if session.direction == 'incoming':
            self.received_calls.append(entry)
        else:
            self.placed_calls.append(entry)
        self.save()

    def _NH_SIPSessionDidFail(self, notification):
        if notification.sender.account is BonjourAccount():
            return
        session = notification.sender
        entry = HistoryEntry.from_session(session)
        if session.direction == 'incoming':
            if notification.data.code == 487 and notification.data.failure_reason == 'Call completed elsewhere':
                self.received_calls.append(entry)
            else:
                self.missed_calls.append(entry)
        else:
            if notification.data.code == 487:
                entry.reason = 'cancelled'
            else:
                entry.reason = '%s (%s)' % (notification.data.reason or notification.data.failure_reason, notification.data.code)
            self.placed_calls.append(entry)
        self.save()


class HistoryEntry(object):
    phone_number_re = re.compile(r'^(?P<number>(0|00|\+)[1-9]\d{7,14})@')

    def __init__(self, remote_identity, target_uri, account_id, call_time, duration, reason=None):
        self.remote_identity = remote_identity
        self.target_uri = target_uri
        self.account_id = account_id
        self.call_time = call_time
        self.duration = duration
        self.reason = reason

    @classmethod
    def from_session(cls, session):
        if session.start_time is None and session.end_time is not None:
            # Session may have anded before it fully started
            session.start_time = session.end_time
        call_time = session.start_time or datetime.now()
        if session.start_time and session.end_time:
            duration = session.end_time - session.start_time
        else:
            duration = None
        remote_identity = session.remote_identity
        remote_uri = '%s@%s' % (remote_identity.uri.user, remote_identity.uri.host)
        match = cls.phone_number_re.match(remote_uri)
        if match:
            remote_uri = match.group('number')
        try:
            contact = next(contact for contact in AddressbookManager().get_contacts() if remote_uri in (addr.uri for addr in contact.uris))
        except StopIteration:
            display_name = remote_identity.display_name
        else:
            display_name = contact.name
        if display_name and display_name != remote_uri:
            remote_identity = '%s <%s>' % (display_name, remote_uri)
        else:
            remote_identity = remote_uri
        return cls(remote_identity, remote_uri, unicode(session.account.id), call_time, duration)

    def __unicode__(self):
        result = unicode(self.remote_identity)
        if self.call_time:
            call_date = self.call_time.date()
            today = date.today()
            days = (today - call_date).days
            if call_date == today:
                result += self.call_time.strftime(" at %H:%M")
            elif days == 1:
                result += self.call_time.strftime(" Yesterday at %H:%M")
            elif days < 7:
                result += self.call_time.strftime(" on %A")
            elif call_date.year == today.year:
                result += self.call_time.strftime(" on %B %d")
            else:
                result += self.call_time.strftime(" on %Y-%m-%d")
        if self.duration:
            seconds = int(self.duration.total_seconds())
            if seconds >= 3600:
                result += """ (%dh%02d'%02d")""" % (seconds / 3600, (seconds % 3600) / 60, seconds % 60)
            else:
                result += """ (%d'%02d")""" % (seconds / 60, seconds % 60)
        elif self.reason:
            result += ' (%s)' % self.reason.title()
        return result


