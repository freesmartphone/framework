"""
Module flags (see command.py)
"""

# 	Copyright (c) 2008 Peter V. Saveliev
#
# 	This file is part of Connexion project.
#
# 	Connexion is free software; you can redistribute it and/or modify
# 	it under the terms of the GNU General Public License as published by
# 	the Free Software Foundation; either version 3 of the License, or
# 	(at your option) any later version.
#
# 	Connexion is distributed in the hope that it will be useful,
# 	but WITHOUT ANY WARRANTY; without even the implied warranty of
# 	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# 	GNU General Public License for more details.
#
# 	You should have received a copy of the GNU General Public License
# 	along with Connexion; if not, write to the Free Software
# 	Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

# ... can create non-leaf nodes in the tree
Begin = 1
# ... takes addition system info
Esoteric = 2
# ... runs immediately anyway
Immediate = 4
# ... pass command execution
Bypass = 8
# ... unique node
Unique = 0x10
# ... hidden node
Hidden = 0x20
# ... force subtree to be restarted
Force = 0x40
# ... transparent node
Transparent = 0x80
# ... internal node
Internal = 0x100
# ... newborn flag
Newborn = 0x200
# ... once ?
Once = 0x400
# ... transparent node for locals upload
LocalsTransparent = 0x800
# ... upoad variables
Upload = 0x1000
# ... stop locals
StopLocals = 0x2000
# ... satellite class, not for direct commands
Satellite = 0x4000
# ... hold the node even if the parent want to run it immediately
Hold = 0x8000