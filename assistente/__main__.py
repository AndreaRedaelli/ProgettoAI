"""Punto di ingresso.

    python -m assistente                  chat
    python -m assistente loop "obiettivo" loop autonomo
    python -m assistente gui              interfaccia grafica
"""

import sys

if sys.argv[1:2] == ["loop"]:
    from .loop import main

    main(sys.argv[2:])
elif sys.argv[1:2] == ["gui"]:
    from .gui import main

    main()
else:
    from .cli import main

    main()
