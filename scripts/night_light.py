"""Scheduled gamma control through one session-owned wlsunset process."""
from datetime import datetime, timedelta, timezone
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile


def clock_minutes(value):
    if not isinstance(value, str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', value):
        raise ValueError('Use a time in HH:MM format')
    hour, minute = map(int, value.split(':'))
    return hour * 60 + minute


def solar_times(day, latitude, longitude):
    """Approximate Almanac for Computers (1990) solar events, as UTC datetimes."""
    if not all(type(v) in (int, float) and math.isfinite(v) for v in (latitude, longitude)) or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError('Invalid sunset coordinates')
    result = []
    for rising in (True, False):
        t = day.timetuple().tm_yday + ((6 if rising else 18) - longitude / 15) / 24
        anomaly = 0.9856 * t - 3.289
        rad = math.radians(anomaly)
        solar = (anomaly + 1.916 * math.sin(rad) + 0.020 * math.sin(2 * rad) + 282.634) % 360
        ascension = math.degrees(math.atan(0.91764 * math.tan(math.radians(solar)))) % 360
        ascension += math.floor(solar / 90) * 90 - math.floor(ascension / 90) * 90
        declination = math.asin(0.39782 * math.sin(math.radians(solar)))
        denominator = math.cos(declination) * math.cos(math.radians(latitude))
        if abs(denominator) < 1e-9: raise ValueError('Sunset scheduling is unavailable at this latitude; choose a time schedule')
        cosine = (math.cos(math.radians(90.833)) - math.sin(declination) * math.sin(math.radians(latitude))) / denominator
        if not -1 <= cosine <= 1: raise ValueError('No sunrise or sunset today; choose a time schedule')
        angle = math.degrees(math.acos(cosine))
        hour = (360 - angle if rising else angle) / 15
        utc_hour = (hour + ascension / 15 - 0.06571 * t - 6.622 - longitude / 15) % 24
        result.append(datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(hours=utc_hour))
    return result


def desired_state(preferences, place, now):
    mode = preferences['nightLightMode']
    start, end = preferences['nightLightStart'], preferences['nightLightEnd']
    if mode == 'sunset':
        if not place: raise ValueError('Waiting for location. Choose a location in Weather or use a time schedule.')
        sunrise, sunset = solar_times(now.date(), place['latitude'], place['longitude'])
        end, start = sunrise.astimezone(now.tzinfo).strftime('%H:%M'), sunset.astimezone(now.tzinfo).strftime('%H:%M')
    first, last = clock_minutes(start), clock_minutes(end)
    minute = now.hour * 60 + now.minute
    scheduled = first <= minute < last if first < last else minute >= first or minute < last
    return preferences['nightLightEnabled'] and (mode == 'manual' or scheduled), start, end


class NightLight:
    def __init__(self, runner):
        self.runner, self.child, self.log = runner, None, None
        self.signature, self.error = None, ''

    def close(self):
        if self.child:
            if self.child.poll() is None:
                try: os.killpg(self.child.pid, signal.SIGTERM)
                except ProcessLookupError: pass
                try: self.child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    try: os.killpg(self.child.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                    self.child.wait(timeout=2)
            self.child = None
        if self.log: self.log.close(); self.log = None

    def sync(self, preferences, place, now=None):
        now = now or datetime.now().astimezone()
        available = self.runner.available('wlsunset')
        wanted, start, end, schedule_error = False, '', '', ''
        try: wanted, start, end = desired_state(preferences, place, now)
        except (ValueError, KeyError) as exc:
            if preferences['nightLightEnabled']: schedule_error = str(exc)
        temperature = preferences['nightLightTemperature']
        signature = (wanted, temperature)
        if signature != self.signature:
            self.close(); self.signature = signature; self.error = ''
            if wanted:
                if not available: self.error = 'Install wlsunset, then restart the shell to enable Night Light.'
                else:
                    try:
                        self.log = tempfile.TemporaryFile(mode='w+')
                        # Both day/night temperatures are warm: no midnight gap in manual mode.
                        argv = [self.runner.executable('wlsunset'), '-T', str(temperature + 1), '-t', str(temperature), '-S', '06:00', '-s', '18:00']
                        helper = Path(__file__).with_name('idle_control.py')
                        self.child = subprocess.Popen([sys.executable, str(helper), '--parent', str(os.getpid()), 'client', *argv],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=self.log, start_new_session=True)
                    except OSError as exc: self.error = 'Could not start Night Light: ' + str(exc)
        if self.child and self.child.poll() is not None:
            self.error = 'wlsunset stopped. Gamma control may be unavailable or owned by another app.'
            self.close()
        if self.log:
            size = os.fstat(self.log.fileno()).st_size
            text = os.pread(self.log.fileno(), min(size, 2048), max(0, size - 2048)).decode(errors='replace')
            if re.search(r'fail|not supported|not available|no gamma', text, re.I):
                self.error = 'Gamma control failed. Check compositor/driver support and stop any other gamma controller. ' + text[-240:].strip()
        return {'enabled': preferences['nightLightEnabled'], 'active': self.child is not None and not self.error,
                'running': self.child is not None, 'available': available, 'temperature': temperature,
                'mode': preferences['nightLightMode'], 'start': start, 'end': end, 'error': schedule_error or self.error}
