#!/usr/bin/env python3
"""progress.py: the progress of a long run over many levels (tools/solveall.py,
tools/reroll.py): levels done out of all, and each level being worked on
with how long it has taken so far.  The run keeps build/progress.txt up to
date (once a second); on a terminal it also shows the bar itself.

    python3 tools/progress.py        (watch a run from another terminal)

Public domain (Unlicense)."""
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(HERE, '..', 'build', 'progress.txt')
WIDTH = 30


def mmss(s):
    s = int(s)
    return '%d:%02d:%02d' % (s // 3600, s // 60 % 60, s % 60) if s >= 3600 else '%d:%02d' % (s // 60, s % 60)


class Progress:
    """started(n) from the workers (through an array shared with them:
    each level's starting time, 0 when not running), finished(n) here, a
    thread writing the status"""

    def __init__(self, total, what='levels', top=256):
        import multiprocessing
        background()
        self.running = multiprocessing.Array('d', top, lock=False)
        self.total, self.what = total, what
        self.done, self.note = 0, ''
        self.t0 = time.time()
        self.stop = False
        self.tty = sys.stdout.isatty()
        self.th = threading.Thread(target=self._loop, daemon=True)
        self.th.start()

    def finished(self, n, note=''):
        self.done += 1
        self.note = note
        self.running[n] = 0

    def line(self):
        now = time.time()
        k = WIDTH * self.done // max(1, self.total)
        run = sorted(((n, t) for n, t in enumerate(self.running) if t), key=lambda x: x[1])
        s = '[%s%s] %d/%d %s, %s' % ('#' * k, '-' * (WIDTH - k), self.done, self.total, self.what,
                                     mmss(now - self.t0))
        if run:
            s += '; working on ' + ', '.join('%d (%s)' % (n, mmss(now - t)) for n, t in run)
        return s

    def _loop(self):
        while not self.stop:
            self.write()
            time.sleep(1)

    def write(self, final=False):
        s = self.line() + (' (finished)' if final else '')
        try:
            with open(FILE + '.tmp', 'w') as f:
                f.write(s + '\n')
            os.replace(FILE + '.tmp', FILE)
        except OSError:
            pass
        if self.tty:
            cols = os.get_terminal_size().columns
            sys.stdout.write('\r\033[K' + s[:cols - 1])
            sys.stdout.flush()

    def print(self, msg):
        """a line of output above the bar"""
        if self.tty:
            sys.stdout.write('\r\033[K')
        print(msg, flush=True)
        if self.tty:
            self.write()

    def close(self):
        self.stop = True
        self.write(final=True)
        if self.tty:
            sys.stdout.write('\n')


# the workers' side: Pool(initializer=init, initargs=(progress.running,))
_running = None


def workers():
    """processes for a long run: GEODE_JOBS (default 8: twenty at once
    heat-soaked the owner's liquid loop, 28 C to 39 C and climbing)"""
    try:
        return max(1, int(os.environ.get('GEODE_JOBS', '8')))
    except ValueError:
        return 8


def background():
    """the lowest priority (nice 19): a long run takes only what's left over,
    never a frame from the emulator the owner is playing in (it once
    lagged mid-level under a run at full priority)"""
    try:
        os.nice(19 - os.nice(0))
    except OSError:
        pass


def init(running):
    global _running
    _running = running
    background()


def started(n):
    if _running is not None:
        _running[n] = time.time()


if __name__ == '__main__':
    last = ''
    try:
        while True:
            try:
                s = open(FILE).read().strip()
            except OSError:
                s = '(no run yet: build/progress.txt)'
            cols = os.get_terminal_size().columns if sys.stdout.isatty() else 200
            sys.stdout.write('\r\033[K' + s[:cols - 1])
            sys.stdout.flush()
            if s.endswith('(finished)'):
                break
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    print()
