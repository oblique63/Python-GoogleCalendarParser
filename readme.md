Python Google Calendar Parser
=============================
This is a parser for Google Calendar's XML atom feed and iCal (.ics) export formats.  I needed 
something like this for a project where I couldn't use Google's python api, and I didn't find 
any practical calendar parsers out there, so I built this one.

Requirements
------------
This module depends on `icalendar`, `beautifulsoup`, and `pytz`. These dependencies are listed in 
the `requirements.txt` file, and may be installed by doing:

    pip install -r requirements.txt


Usage
-----
The goal of this module is to allow for the simple manipulation of calendar events like they were 
any other python data structure. As such, the `CalendarParser` object acts as a simple list-like 
interface for the calendar's events, which themselves are plain dictionaries with straight-forward 
keys containing the properties of the event.

`CalendarParser` can accept either url or local file inputs:


```python
from calendar_parser import CalendarParser
    
xml_feed = "https://www.google.com/calendar/feeds/.../basic"
xml_file = "/path/to/file.xml"
    
ics_url = "https://www.google.com/calendar/ical/.../basic.ics"
ics_file = "/path/to/file.ics"
  
cal = CalendarParser( xml_url=xml_feed [, xml_file=xml_file, ics_url=ics_url, ics_file=ics_file ] )
```

The calendar data isn't fetched until you request to parse it.  By default, the `parse_calendar` method 
returns a generator to let you iterate through the event dictionaries as they're being parsed.

```python
for event in cal.parse_calendar():
    print event["name"]
```

However, you can force the parser to return a list, thus parsing all the events at once.

```python
redundant_event_list = cal.parse_calendar(force_list=True)
```

In the case that you plan on using iCal and xml sources interchangeably, you can tell the parser which 
source to use.

```python
cal.xml_url = xml_feed
cal.ics_url = ics_url

ics_events = cal.parse_calendar(force_list=True, use_ics=True)
xml_events = cal.parse_calendar(force_list=True, use_xml=True)
```
_(not all of the same event/calendar properties are available from both ics and xml resources, 
so it's not an unlikely scenario)_

Since this is possible, and the parser overwrites its events list every time it parses a resource, 
if you don't want to overwrite your existing events list, you can specify that as well.

```python
cal.parse_calendar(force_list=True, use_xml=True)

for event in cal.parse_calendar(use_ics=True, overwrite_events=False):
    # Just want to see what I'm missing out on, but don't want to
    # commit to using the iCal data
    ...
    
    # Oh and look, I can still access the xml event data in here!
    print event.name in cal.events
```

Also, as was just alluded to, you may access any of an event's properties either as keys in a  
dictionary (`event.name`), or as attributes of an object (`event["name"]`).

And you can use the names of events like keys in a dictionary on the `CalendarParser` object.

```python
from datetime import datetime

if  "my birthday" in cal and cal["my birthday"].start_time.date() == datetime.today().date():
    print "Happy Birthday To Me!"
```

Or look them up by their index like a list.

```python
top_event = cal[0]
top_5_events = cal[0:5]
```

And finally, since Google's calendar output isn't usually sorted chronologically, you have the 
option to sort them as you wish.

```python
latest_first = cal.sort_by_latest()
cal.sort_by_oldest(sort_in_place=True)
```

A fun side-effect of this, is that you may also compare events (based on their `start_time`) 
like normal datetime objects.

```python
if cal[0] > cal[1]:
    print "The events are sorted by latest-first!"
else:
    print "The events are not sorted by latest-first."
```

Enjoy!

Properties
----------
- CalendarParser
    - title
    - subtitle
    - author
    - email
    - calendar [name]
    - time_zone
    - last_updated
    - date_published
    - events

- CalendarEvent
    - name
    - description
    - location
    - start_time
    - end_time
    - all_day
    - repeats
    - repeat_freq
    - repeat_day
    - repeat_month
    - repeat_until


Licensing
---------
This code is released under the [Mozilla Public License](http://www.mozilla.org/MPL/MPL-1.1.html).
Copyright &copy; 2011, Enrique Gavidia
