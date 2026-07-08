"""Shared test bootstrap.

WMI workaround: on some Windows machines the WMI service intermittently
wedges, and ``platform.win32_ver()`` — reached transitively on SQLAlchemy's
first import via ``platform.machine()`` — blocks forever inside its WMI query
(observed 2026-07-08: pytest "collecting ..." hung for minutes system-wide).

Patching ``platform._win32_ver`` to the stdlib's own no-WMI fallback keeps
test collection independent of WMI health. On healthy machines this only
skips an informational lookup; no behavior of the app under test changes.
"""
import platform

# Mirrors the stdlib fallback: (version, csd, ptype, is_client) with WMI skipped;
# win32_ver() then falls back to sys.getwindowsversion() for the version.
platform._win32_ver = lambda version, csd, ptype: (version, csd, ptype, True)
