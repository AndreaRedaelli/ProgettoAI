"""Punto di ingresso.

    python -m assistente                  chat
    python -m assistente loop "obiettivo" loop autonomo
"""

import sys

if sys.argv[1:2] == ["loop"]:
    from .loop import main

    main(sys.argv[2:])
else:
    from .cli import main

    main()
