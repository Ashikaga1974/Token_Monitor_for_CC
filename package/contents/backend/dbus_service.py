"""D-Bus Service for Token Monitor for Claude Code to enable on-demand activation by the Plasma widget."""

import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib
import json
import logging
import threading
import time

from .server import run_server, get_cached_or_fresh_stats

logger = logging.getLogger(__name__)

class TokenMonitorDBusService(dbus.service.Object):
    def __init__(self, bus_name):
        super().__init__(bus_name, "/com/buellsunited/TokenMonitor")

    @dbus.service.method("com.buellsunited.TokenMonitor", in_signature="b", out_signature="s")
    def GetStats(self, force):
        """Returns metrics as JSON string. Triggers a background refresh if requested."""
        stats = get_cached_or_fresh_stats(force=bool(force))
        return json.dumps(stats)

    @dbus.service.method("com.buellsunited.TokenMonitor", in_signature="", out_signature="s")
    def Ping(self):
        return "pong"


def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    session_bus = dbus.SessionBus()
    bus_name = dbus.service.BusName("com.buellsunited.TokenMonitor", session_bus)
    service = TokenMonitorDBusService(bus_name)

    # Start HTTP server in a separate thread (for QML XMLHttpRequest)
    t = threading.Thread(target=run_server, args=(48291,), daemon=True)
    t.start()

    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        loop.quit()

if __name__ == "__main__":
    main()
