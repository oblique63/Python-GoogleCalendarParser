"A Google Calendar Parser"

from datetime import datetime, date, timedelta
from time import strptime, mktime
from xml.sax.saxutils import unescape
from urllib2 import urlopen

# From Requirements.txt
from pytz import timezone
from icalendar.cal import Calendar, Event
from BeautifulSoup import BeautifulStoneSoup, Tag


TIME_FORMATS = (
    "%a %b %d, %Y %I:%M%p",
    "%a %b %d, %Y %I%p",
    "%a %b %d, %Y",
    "%Y-%m-%dT%H:%M:%S"
)

def _parse_time(time_str, reference_date=None):
    """\
    Parses a calendar time string, and outputs a datetime object of the specified time.
    Only compatible with the time formats listed in the TIME_FORMATS tuple.

    'reference_date' is another time-string, used when the original time_str doesn't contain any date information.
    """
    time_struct = None
    if len(time_str.split()) == 1:
        if "." in time_str:
            time_str = time_str.rsplit('.', 1)[0]
        else:
            assert reference_date, "Hour-only time strings need a reference date string."
            time_str = " ".join(reference_date.split()[:4]) + " " + time_str

    for time_format in TIME_FORMATS:
        try:
            time_struct = strptime(time_str, time_format)
        except ValueError:
            pass

    if time_struct == None:
        raise ValueError("Unsopported time string format: %s" % (time_str))

    return datetime.fromtimestamp(mktime(time_struct))


def _fix_timezone(datetime_obj, time_zone):
    """\
    Adjusts time relative to the calendar's timezone,
    then removes the datetime object's timezone property.
    """
    if type(datetime_obj) is datetime and datetime_obj.tzinfo is not None:
        return datetime_obj.astimezone(time_zone).replace(tzinfo=None)

    elif type(datetime_obj) is date:
        return datetime(datetime_obj.year, datetime_obj.month, datetime_obj.day)
    
    return datetime_obj

def _multi_replace(string, replace_dict):
    "Replaces multiple items in a string, where replace_dict consists of {value_to_be_removed: replced_by, etc...}"
    for key, value in replace_dict.iteritems():
        string = string.replace(str(key), str(value))
    return string

def _normalize(data_string, convert_whitespace=False):
    "Removes various markup artifacts and returns a normal python string."
    new_string = unescape(str(data_string))
    new_string = _multi_replace(new_string, {
        '&nbsp;': ' ', '&quot;': '"', '&brvbar;': '|', "&#39;": "'", "\\": ""
    })
    new_string = new_string.strip()

    if convert_whitespace:
        return " ".join(new_string.split())
        
    return new_string


class CalendarEvent(dict):
    """\
    A modified dictionary that allows accessing and modifying the main properties of a calendar event
    as both attributes, and dictionary keys; i.e. 'event["name"]' is the same as using 'event.name'

    Only the following event-specific properties may be accessed/modified as attributes:
    "name", "description", "location", "start_time", "end_time", "all_day",
    "repeats", "repeat_freq", "repeat_day", "repeat_month", "repeat_until"

    CalendarEvents may also be compared using the >, >=, <, <=, comparison operators, which compare
    the starting times of the events.
    """
    __slots__ = ( "name", "description", "location", "start_time", "end_time", "all_day",
                  "repeats", "repeat_freq", "repeat_day", "repeat_month", "repeat_until" )
    
    def __getattr__(self, key):
        if key in self.__slots__:
            return self[key]
        else:
            return dict.__getattribute__(self, key)
        
    def __setattr__(self, key, value):
        if key in self.__slots__:
            self[key] = value
        else:
            raise AttributeError("dict attributes are not modifiable.")
        
    def __lt__(self, other):
        assert type(other) is CalendarEvent, "Both objects must be CalendarEvents to compare."
        return self["start_time"] < other["start_time"]
    
    def __le__(self, other):
        assert type(other) is CalendarEvent, "Both objects must be CalendarEvents to compare."
        return self["start_time"] <= other["start_time"]

    def __gt__(self, other):
        assert type(other) is CalendarEvent, "Both objects must be CalendarEvents to compare."
        return self["start_time"] > other["start_time"]

    def __ge__(self, other):
        assert type(other) is CalendarEvent, "Both objects must be CalendarEvents to compare."
        return self["start_time"] >= other["start_time"]


class CalendarParser(object):
    """\
    A practical calendar parser for Google Calendar's two output formats: XML, and iCal (.ics).
    Stores events as a list of dictionaries with self-describing attributes.
    Accepts url resources as well as local xml/ics files.
    Certain fields/properties are not available when parsing ics resources.
    """
    # TODO: Accept calendarIDs and support google's REST api

    def __init__(self, ics_url=None, xml_url=None, ics_file=None, xml_file=None):
        self.ics_file = ics_file
        self.ics_url = ics_url
        self.xml_file = xml_file
        self.xml_url = xml_url
        self.time_zone = None
        self.calendar = None
        self.title = ""
        self.subtitle = ""
        self.author = ""
        self.email = ""
        self.last_updated = None
        self.date_published = None
        self.events = []

    def __len__(self):
        return len(self.events)

    def __iter__(self):
        return self.events.__iter__()

    def __reversed__(self):
        return reversed(self.events)

    def __contains__(self, item):
        if type(item) is not str:
            return item in self.events
        
        for event in self.events:
            if event["name"].lower() == item.lower():
                return True
            
        return False

    def __getitem__(self, item):
        if type(item) is str:
            event_list = []
            for event in self.events:
                if event["name"].lower() == item.lower():
                    event_list.append(event)
                
            if len(event_list) == 0:
                raise LookupError("'%s' is not an event in this calendar." % (item))
            if len(event_list) == 1:
                return event_list[0]
            else:
                return event_list
        else:
            return self.events[item]


    def keys(self):
        "Returns the names of all the parsed events, which may be used as lookup-keys on the parser object."
        return [event["name"] for event in self.events]


    def sort_by_latest(self, sort_in_place=False):
        "Returns a list of the parsed events, where the newest events are listed first."
        sorted_events = sorted(self.events, reverse=True)
        if sort_in_place:
            self.events = sorted_events
        return sorted_events

    def sort_by_oldest(self, sort_in_place=False):
        "Returns a list of the parsed events, where the oldest events are listed first."
        sorted_events = sorted(self.events)
        if sort_in_place:
            self.events = sorted_events
        return sorted_events


    def fetch_calendar(self, force_xml=False, force_ics=False):
        "Fetches the calendar data from an XML/.ics resource in preperation for parsing."
        cal_data = None
        if self.xml_url:
            cal_data = urlopen(self.xml_url)
        elif self.ics_url:
            cal_data = urlopen(self.ics_url)
        elif self.xml_file:
            cal_data = open(self.xml_file, "rb")
        elif self.ics_file:
            cal_data = open(self.ics_file, "rb")
        else:
            raise UnboundLocalError("No calendar url or file path has been set.")

        cal_str = cal_data.read()
        cal_data.close()

        if (self.xml_url or self.xml_file) and not force_ics:
            self.calendar = BeautifulStoneSoup(_normalize(cal_str, True))
        elif (self.ics_url or self.ics_file) and not force_xml:
            self.calendar = Calendar.from_ical(cal_str)

        return self.calendar


    def parse_xml(self, overwrite_events=True):
        "Returns a generator of Event dictionaries from an XML atom feed."
        
        assert self.xml_url or self.xml_url, "No xml resource has been set."
        self.calendar = self.fetch_calendar(force_xml=True).contents[1]
        metadata = self.calendar.contents[1:3]
        
        self.title = metadata[1].contents[0].contents[0]
        self.subtitle = metadata[1].contents[1].next
        self.author = metadata[1].contents[6].next.next.next
        self.email = metadata[1].contents[6].next.contents[1].next
        self.time_zone = timezone(metadata[1].contents[6].contents[5].attrs[0][1])
        self.last_updated = _parse_time(metadata[0].next)
        self.date_published = _parse_time(
            metadata[1].contents[6].contents[5].next.next.contents[1].next)
        
        raw_events = self.calendar.contents[3:]

        if overwrite_events:
            self.events = []
        
        for event in raw_events:
            event_dict = CalendarEvent()
            event_dict["name"] = _normalize(event.next.next)
            event_dict["repeats"] = False

            for content in event.contents[2]:
                if isinstance(content, Tag):
                    content = content.contents[0]

                if "Recurring Event" in content:
                    event_dict["repeats"] = True

                elif event_dict["repeats"]:
                    if "First start:" in content:
                        rep_info = content.split()[2:-1]
                        rep_date = rep_info[0].split('-')

                        # Not enough info to determine how often the event repeats...
                        #event_dict['repeat_month'] = rep_date[1]  # "YEARLY"
                        #event_dict['repeat_day'] = rep_date[2]    # "MONTHLY"

                        rep_date = map(int, rep_date)
                        if len(rep_info) == 2:
                            rep_time = map(int, rep_info[1].split(':'))
                            event_dict["start_time"] = datetime( *(rep_date + rep_time) )
                        else:
                            event_dict["start_time"] = datetime(*rep_date)

                    elif "Duration:" in content:
                        seconds = int(content.split()[-1])
                        event_dict["end_time"] = event_dict["start_time"] + timedelta(seconds=seconds)
                        

                elif "When: " in content:
                    when = event.contents[1].next.replace("When: ", "", 1)

                    if len(when.split()) > 4:
                        # Remove the timezone
                        when = when.rsplit(" ", 1)[0]

                    when = when.split(" to ")
                    if len(when) == 2:
                        start, end = when
                        event_dict["end_time"] = _parse_time(end, start)
                    else:
                        start = when[0]
                    event_dict["start_time"] = _parse_time(start)

                    if not "end_time" in event_dict \
                    and event_dict["start_time"].hour == 0 \
                    and event_dict["start_time"].minute == 0:
                        event_dict["all_day"] = True
                        event_dict["end_time"] = event_dict["start_time"] + timedelta(days=1)
                    else:
                        event_dict["all_day"] = False
                    

                elif "Where: " in content:
                    event_dict["location"] = _normalize(content).replace("Where: ", "")

                elif "Event Description: " in content:
                    event_dict["description"] = _normalize(content).replace("Event Description: ", "")

            if overwrite_events:
                self.events.append(event_dict)

            yield event_dict

                
    def parse_ics(self, overwrite_events=True):
        "Returns a generator of Event dictionaries from an iCal (.ics) file."
        assert self.ics_url or self.ics_url, "No ics resource has been set."

        # Returns an icalendar.Calendar object.
        self.fetch_calendar(force_ics=True)

        self.time_zone = timezone(str(self.calendar["x-wr-timezone"]))
        self.title = str(self.calendar["x-wr-calname"])

        if overwrite_events:
            self.events = []

        for event in self.calendar.walk():
            if isinstance(event, Event):
                event_dict = CalendarEvent()
                if "SUMMARY" in event:
                    event_dict["name"] = _normalize(event["summary"])
                if "DESCRIPTION" in event:
                    event_dict["description"] = _normalize(event["description"])
                if "LOCATION" in event and event["location"]:
                    event_dict["location"] = _normalize(event["location"])
                if "DTSTART" in event:
                    event_dict["start_time"] = _fix_timezone(event["dtstart"].dt, self.time_zone)
                if "DTEND" in event:
                    event_dict["end_time"] = _fix_timezone(event["dtend"].dt, self.time_zone)
                
                event_dict["repeats"] = False
                if "RRULE" in event:
                    rep_dict = event["RRULE"]

                    event_dict["repeats"] = True
                    event_dict["repeat_freq"] = rep_dict["FREQ"][0]

                    if event_dict["repeat_freq"] == "YEARLY":
                        event_dict["repeat_day"] = event_dict["start_time"].day
                        event_dict["repeat_month"] = event_dict["start_time"].month

                        if event_dict["start_time"].hour == 0 \
                        and event_dict["start_time"].minute == 0 \
                        and (event_dict["end_time"] - event_dict["start_time"]) == timedelta(days=1):
                            event_dict["all_day"] = True
                        else:
                            event_dict["all_day"] = False

                    if "BYDAY" in rep_dict:
                        event_dict["repeat_day"] = rep_dict["BYDAY"][0]
                    elif "BYMONTHDAY" in rep_dict:
                        event_dict["repeat_day"] = rep_dict["BYMONTHDAY"][0]

                    if "BYMONTH" in rep_dict:
                        event_dict["repeat_month"] = rep_dict["BYMONTH"][0]

                    if "UNTIL" in rep_dict:
                        event_dict["repeat_until"] = _fix_timezone(rep_dict["UNTIL"][0], self.time_zone)

                if overwrite_events:
                    self.events.append(event_dict)

                yield event_dict


    def parse_calendar(self, force_list=False, use_xml=False, use_ics=False, overwrite_events=True):
        "Parses the calendar at the specified resource path.  Returns a generator of CalendarEvents."
        generator = None
        if (self.ics_url or self.ics_file) and (use_ics or not use_xml):
            generator = self.parse_ics(overwrite_events)
            
        elif (self.xml_url or self.xml_file) and (use_xml or not use_ics):
            generator = self.parse_xml(overwrite_events)
            
        if force_list:
            return [event for event in generator]
        else:
            return generator
