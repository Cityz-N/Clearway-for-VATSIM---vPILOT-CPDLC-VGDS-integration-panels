"""Double-click this file to start Clearway without a console window.

Windows runs .pyw files with pythonw.exe, so only the tray icon appears.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import clearway_app  # noqa: E402

clearway_app.main()
