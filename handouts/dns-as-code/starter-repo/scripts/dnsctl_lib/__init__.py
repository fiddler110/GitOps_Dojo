"""Supporting library modules for scripts/dnsctl.py.

dnsctl.py stays the single CLI entry point (command handlers + argparse
tree); this package holds the stateless logic those handlers call into -
env/credential loading, git/gh/dnscontrol process wrappers, dnsconfig.js
record parsing, and output rendering.
"""
