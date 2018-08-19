import logging

import time
from datetime import datetime, date, time, timezone
import locale
import pytz

import caldav
from caldav.elements import dav, cdav

from kalliope.core.NeuronModule import NeuronModule, InvalidParameterException

logging.basicConfig()
logger = logging.getLogger("kalliope")


class Kaldav (NeuronModule):
    def __init__(self, **kwargs):
        super(Kaldav, self).__init__(**kwargs)

        # get parameters form the neuron
        self.configuration = {
            'url': kwargs.get('url', None),
            'action': kwargs.get('action', None),
            'max_results': kwargs.get('max_results', 1),
            'name': kwargs.get('name', None),
            'start_date': kwargs.get('start_date', None),
            'end_date': kwargs.get('end_date', None),
            'date_format': kwargs.get('date_format', '%b %d %Y %I:%M%p'),
            'full_day': kwargs.get('full_day', False),
            'reminder': kwargs.get('reminder', False),
            # 'vevent_date_format': kwargs.get('vevent_date_format', "%Y%m%dT%H%M00Z"),
            'location': kwargs.get('location', None),
            'timezone': kwargs.get('timezone', None)
        }

        # check parameters
        if self._is_parameters_ok():
            self.response = {
                'action': self.configuration['action']
            }

            if self.configuration['action'] == "search":
                events = self.search_event(self.configuration['start_date'], self.configuration['end_date'])
                if events is not False:
                    self.response['events'] = events
            elif self.configuration['action'] == "create":
                self.create_event()
            elif self.configuration['action'] == 'delete':
                pass

            self.say(self.response)

    def get_calendars(self):
        client = caldav.DAVClient(self.configuration['url'])
        principal = client.principal()
        calendars = principal.calendars()
        return calendars

    def create_event(self):
        logger.debug('Creating an event')
        calendars = self.get_calendars()
        calendar = calendars[0]
        logger.debug("Using calendar %s" % calendar)

        if len(calendars) > 0:
            calendar = calendars[0]

            start = datetime.datetime.strptime(
                self.configuration['start_date'],
                self.configuration['date_format'])

            end = datetime.datetime.strptime(
                self.configuration['end_date'],
                self.configuration['date_format'])

            logger.debug("Start date: %s" % start)
            logger.debug("End date: %s" % end)

            # Manage locales.
            if self.configuration['timezone'] is not None:
                logger.debug('Timezone set to %s, converting.' % self.configuration['timezone'])
                local = pytz.timezone(self.configuration['timezone'])
                # Start date:
                start_local = local.localize(start, is_dst=None)
                # Override start with utc time.
                start = start_local.astimezone(pytz.utc)

                # End date:
                end_local = local.localize(end, is_dst=None)
                # Override end with utc time.
                end = end_local.astimezone(pytz.utc)

                # Debug
                logger.debug("start date local time: %s start date utc: %s "% (start_local, start))
                logger.debug("end date local time: %s end date utc: %s "% (end_local, end))

            if self.configuration['full_day'] is True:
                start_str = "DTSTART;VALUE=DATE:" + start.strftime("%Y%m%d")
                end_str = "DTEND;VALUE=DATE:" + end.strftime("%Y%m%d")
            else: 
                start_str = "DTSTART:" + start.strftime("%Y%m%dT%H%M00Z")
                end_str = "DTEND:" + end.strftime("%Y%m%dT%H%M00Z")
            # 20180528T180000Z
            # 20180528T190000Z

            vcal = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Sabre//Sabre VObject 4.1.2//EN
CALSCALE:GREGORIAN
BEGIN:VEVENT
SUMMARY:""" + self.configuration['name']

            if self.configuration['location'] is not None:
                vcal += """
LOCATION:""" + self.configuration['location']

            vcal += """
""" + start_str + """
""" + end_str

            if self.configuration['reminder'] is not None:
                vcal += """
BEGIN:VALARM
TRIGGER:-PT""" + self.configuration['reminder'] + """M
ACTION:DISPLAY
DESCRIPTION:""" + self.configuration['name'] + """
END:VALARM"""

            vcal += """
END:VEVENT
END:VCALENDAR
"""

        logger.debug(vcal)
        event = calendar.add_event(vcal)
        # event = self.configuration['name']
        logger.debug("Event %s created" % event)

    def search_event(self, start, end=None):
        logger.debug('Searching event')
        calendars = self.get_calendars()

        if len(calendars) > 0:
            calendar = calendars[0]
            logger.debug("Using calendar %s" % calendar)

            if start is None:
                # fix me: workaround for getting time in utc
                today = datetime.today()
                start = today.replace(hour=today.hour - 2)
                # catch time out of 24 hours range
                if start.hour is -1:
                    start.replace(hour=23)
                elif start.hour is -2:
                    start.replace(hour=22)
            else:
                # TODO: transform in datetime
                pass
            if end is None:
                # using end of today as default end time
                end = start.replace(day=start.day + 1, hour=00, minute=00, second=00, microsecond=00)
                # catch time out of 24 hours range
                if end.hour is 24:
                    end.replace(hour=00)
            else:
                # TODO: transform in datetime
                pass
            logger.debug("Looking for events between %s and %s" % (start, end))
            results = calendar.date_search(start, end)

            events = []
            count = 0
            for event in results:
                ## fix me: workaround for taking care of max_results
                if count <= self.configuration['max_results']:
                    e = Kvevent(event.data)
                    logger.debug("Found event: %s" % e)
                    ## read start and end time
                    start_event = str(e.get_property('DTSTART'))
                    end_event = str(e.get_property('DTEND'))
                    
                    #logger.debug(e.get_property('DTSTART'))
                    #logger.debug(e.get_property('DTEND'))
                    ## split start and end time into year, month, day, hour, minute
                    s_year = start_event[2:5]
                    s_month = start_event[6:7]
                    s_day = start_event[8:9]
                    # fix me: workaround for transforming hour back to cest
                    s_hour_utc = start_event[11:12]
                    s_hour_cest = int(s_hour_utc) + 2
                    s_minute = start_event[13:14]

                    e_year = end_event[2:5]
                    e_month = end_event[6:7]
                    e_day = end_event[8:9]
                    # fix me: workaround for transforming hour back to cest
                    e_hour_utc = end_event[11:12]
                    e_hour_cest = int(e_hour_utc) + 2
                    e_minute = end_event[13:14]

                    events.append({
                        'name': e.get_property('SUMMARY'),
                        'time': { 's_year': s_year, 's_month': s_month, 's_day': s_day, 's_hour_cest': s_hour_cest, 's_minute': s_minute, 'e_year': e_year, 'e_month': e_month, 'e_day': e_day, 'e_hour_cest': e_hour_cest, 'e_minute': e_minute}
                    })
                    count = count + 1

            logger.debug(events)
            return events
        return False

    def _is_parameters_ok(self):
        """
        Check if received parameters are ok to perform operations in the neuron
        :return: true if parameters are ok, raise an exception otherwise
        .. raises:: InvalidParameterException
        """

        if self.configuration['url'] is None:
            raise InvalidParameterException("CalDav requires an URL.")

        if self.configuration['action'] is None:
            raise InvalidParameterException("CalDav requires an action.")

        return True


class Kvevent():
    def __init__(self, vevent_string):
        logger.debug("Creating Kvevent:\n %s" % vevent_string)
        self.properties = {}
        # Properties can be there twice like "END".
        self.properties = vevent_string.splitlines()

    def get_property(self, name):
        logger.debug('looking for property %s' % name)
        results = []
        for line in self.properties:
            items = line.split(':')
            # logger.debug('name = %s - items0 = %s' % (name, items[0]))
            if name == items[0]:
                logger.debug('found property %s: %s - %s' % (name, items[0], items[1]))
                results.append(items[1])
        return results
