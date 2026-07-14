# Copyright (C) 2024–2026 Eric Hernandez
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import sys
from pathlib import Path

# Base directory of bundled app
base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))

# PyInstaller one-folder build puts things under _internal
internal = base / "_internal"

# Prepend both possible locations to PATH
os.environ["PATH"] = (
    str(internal) + os.pathsep +
    str(base) + os.pathsep +
    os.environ.get("PATH", "")
)