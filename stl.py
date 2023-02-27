#!/usr/bin/env python3
from docopt import docopt, DocoptExit
from dotenv import load_dotenv

from stl.command.stl_command import StlCommand


def main():
    load_dotenv()
    try:
        arguments = docopt(str(StlCommand.__doc__))
        StlCommand(arguments).execute()
    except DocoptExit as de:
        print(de)
        exit(1)


if __name__ == "__main__":
    main()
