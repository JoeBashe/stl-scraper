#!/usr/bin/env python3
from docopt import docopt, DocoptExit

from stl.command.StlCommand import StlCommand


def main():
    """CLI entry point."""
    arguments = []
    try:
        # Parse arguments, use file docstring as a parameter definition
        arguments = docopt(str(StlCommand.__doc__))
    except DocoptExit as de:
        print(de)
        exit(1)

    StlCommand.execute(arguments)


if __name__ == "__main__":
    main()