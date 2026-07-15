"""Enable ``python -m planfile`` as an alias for the ``planfile`` console script.

Without this module the package could only be executed via the installed
``planfile`` entry point or ``python -m planfile.cli``. Adding a top-level
``__main__`` makes ``python -m planfile ...`` behave identically to the CLI,
which is what most tooling and documentation expects.
"""

from planfile.cli.commands import main

if __name__ == "__main__":
    main()
