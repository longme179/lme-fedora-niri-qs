"""One interactive nmcli attempt; no persistent monitor or password on disk/argv."""
import re
import time

from command_runner import CommandError

ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
PROMPT = re.compile(r'(?:^|[\r\n])(?:Password|Key) \(802-11-wireless-security\.(?:psk|wep-key[0-3])\):')
PHASE = re.compile(r'(?:^|[\r\n])[|/\\-] (connecting \([^)]+\)|connected[^\r\n]*)')
IP_PHASES = {'connecting (getting IP configuration)', 'connecting (checking IP connectivity)',
             'connecting (starting secondary connections)'}


class AuthenticationError(CommandError):
    pass


class Attempt:
    def __init__(self, run, interface, password, *, clock=time.monotonic):
        self.run, self.interface, self.has_password, self.clock = run, interface, bool(password), clock
        self.started = clock()
        self.authenticated, self.probed, self.path = False, False, ''

    def active(self):
        value = self.run('nmcli', '-g', 'GENERAL.STATE,GENERAL.CON-PATH', 'device', 'show', self.interface, timeout=2)
        lines = value.splitlines()
        if len(lines) < 2: return 0, ''
        try: state = int(lines[0].split()[0])
        except (ValueError, IndexError): return 0, ''
        path = lines[1].strip()
        return state, path if path.startswith('/org/freedesktop/NetworkManager/ActiveConnection/') else ''

    def capture(self):
        if self.probed: return
        self.probed = True
        try:
            state, path = self.active()
            if 40 <= state < 100: self.path = path
        except (CommandError, OSError, ValueError): pass

    def reject(self, message):
        if not self.path:
            self.probed = False
            self.capture()
        raise AuthenticationError(message)

    def __call__(self, stdout, stderr):
        def text(value): return value.decode('utf-8', 'replace') if isinstance(value, bytes) else value or ''
        output = ANSI.sub('', text(stdout)+'\n'+text(stderr))
        prompts, phases = len(PROMPT.findall(output)), PHASE.findall(output)
        if prompts or phases: self.capture()
        if any(phase in IP_PHASES for phase in phases): self.authenticated = True
        if prompts and not self.has_password:
            self.reject('Enter a Wi-Fi password to connect.')
        if prompts > 1:
            self.reject('Wi-Fi requested the password again. Check it and try again.')
        if not self.authenticated and self.clock()-self.started >= 15:
            try:
                state, path = self.active()
                if 40 <= state < 70: self.path = path
                if 70 <= state <= 100 and path:
                    self.authenticated = True
                    return
            except (CommandError, OSError, ValueError): pass
            raise AuthenticationError('Wi-Fi authentication did not finish. Check the password or signal and try again.')

    def cancel(self):
        if not self.path: return
        try:
            state, path = self.active()
            if path == self.path and 40 <= state < 70:
                self.run('nmcli', '--wait', '0', 'device', 'disconnect', self.interface, timeout=3)
        except (CommandError, OSError, ValueError): pass


def connect(run, args, interface, password):
    attempt = Attempt(run, interface, password)
    try:
        run('nmcli', '--pretty', '--wait', '45', '--ask', *args, input=password+'\n', timeout=50, observe=attempt)
    except AuthenticationError:
        attempt.cancel()
        raise
    except CommandError as error:
        detail = str(error).lower()
        if 'secrets were required' in detail or 'no secrets' in detail:
            raise AuthenticationError('Wi-Fi needs a valid password. Check it and try again.') from None
        if 'timed out' in detail or 'timeout' in detail:
            raise CommandError('Wi-Fi connection timed out. Check the signal and try again.') from None
        raise
    return 'Wi-Fi connected'
