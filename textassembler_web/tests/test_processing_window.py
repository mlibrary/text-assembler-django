from django.test import SimpleTestCase
import datetime

from textassembler_web.ln_api import check_window


def set_weekday(now, weekday):
    while now.weekday() != weekday:
        now += datetime.timedelta(1)
    return now


class ProcessingWindowTestCase(SimpleTestCase):

    def testProperTimeWindow(self):
        now = datetime.datetime.now()
        # Is Friday at 22:59 inside the download window? NO
        now = set_weekday(now, 4)
        now = now.replace(hour=21, minute=59)
        inside_window, _start = check_window(now)
        self.assertFalse(inside_window, "Friday at 21:59 should be outside window")
        # Is Friday at 22:00 inside the download window? YES
        now = now.replace(hour=22, minute=00)
        inside_window, _start = check_window(now)
        self.assertTrue(inside_window)
        # Is Saturday at noon? YES
        now = set_weekday(now, 5)
        now = now.replace(hour=12)
        inside_window, _start = check_window(now)
        self.assertTrue(inside_window)
        # Is Sunday at 23:59? YES
        now = set_weekday(now, 6)
        now = now.replace(hour=23, minute=59)
        inside_window, _start = check_window(now)
        self.assertTrue(inside_window)
        # Is Monday at 05:59? YES
        now = set_weekday(now, 0)
        now = now.replace(hour=5)
        inside_window, _start = check_window(now)
        self.assertTrue(inside_window)
        # Is Monday at 06:00? NO
        now = now.replace(hour=6, minute=0)
        inside_window, _start = check_window(now)
        self.assertFalse(inside_window)
        # Is Tuesday at 23:30? NO
        now = set_weekday(now, 1)
        now = now.replace(hour=23, minute=30)
        inside_window, _start = check_window(now)
        self.assertFalse(inside_window)
