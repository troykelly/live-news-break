import datetime
import pytz
from jinja2 import Environment, BaseLoader, Template
from typing import Optional

class TemplateHandlers:
    def __init__(self, current_time: datetime.datetime, station_name: str, station_city: str, station_country: str, station_timezone_name: str, newsreader_name: str, have_weather: bool):
        """Initializes the handlers with given station and newsreader details."""
        self.current_time = current_time
        self.current_time = self.current_time.astimezone(pytz.timezone(station_timezone_name))
        self.station_name = station_name
        self.station_city = station_city
        self.station_country = station_country
        self.station_timezone = pytz.timezone(station_timezone_name)
        self.newsreader_name = newsreader_name
        self.have_weather = have_weather

    @property
    def current_day_name(self) -> str:
        """Returns the current day name."""
        return self.current_time.strftime('%A')

    @property
    def current_hour_24(self) -> str:
        """Returns the current hour in word representation for 24-hour format."""
        hour_24 = self.current_time.hour
        hour_words = [
            "midnight", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
            "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty",
            "twenty-one", "twenty-two", "twenty-three"
        ]
        return hour_words[hour_24]

    @property
    def current_hour_12(self) -> str:
        """Returns the current hour in word representation for 12-hour format."""
        hour_12 = int(self.current_time.strftime('%I'))  # Using %I for 12-hour format
        hour_words = [
            "", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"
        ]
        return hour_words[hour_12]

    @property
    def current_minute(self) -> int:
        """Returns the current minute."""
        return self.current_time.minute

    @property
    def period_of_day(self) -> str:
        """Returns 'morning', 'afternoon' or 'evening' based on the current time."""
        hour = self.current_time.hour
        if 5 <= hour < 12:
            return 'morning'
        elif 12 <= hour < 18:
            return 'afternoon'
        else:
            return 'evening'

    @property
    def is_top_of_the_hour(self) -> bool:
        """Returns True if the current minute is zero, else False."""
        return self.current_time.minute == 0

def get_template_environment(handlers: TemplateHandlers) -> Environment:
    """Sets up the Jinja2 environment with custom filters."""
    env = Environment(loader=BaseLoader())
    env.globals.update({
        'current_day_name': handlers.current_day_name,
        'current_hour_12': handlers.current_hour_12,
        'current_hour_24': handlers.current_hour_24,
        'current_minute': handlers.current_minute,
        'period_of_day': handlers.period_of_day,
        'is_top_of_the_hour': handlers.is_top_of_the_hour,
        'station_name': handlers.station_name,
        'station_city': handlers.station_city,
        'station_country': handlers.station_country,
        'station_timezone_name': handlers.station_timezone.zone,
        'newsreader_name': handlers.newsreader_name,
        'have_weather': handlers.have_weather
    })
    return env

def render_template(template_string: str, handlers: TemplateHandlers) -> str:
    """Renders the template string using the Jinja2 environment and handlers."""
    env = get_template_environment(handlers)
    template = env.from_string(template_string)
    return template.render()