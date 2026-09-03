"""Runs a conformance check: python3 -m notation <module exporting MANIFEST>"""

import sys

from .conformance import main

sys.exit(main(sys.argv))
