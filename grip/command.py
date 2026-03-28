"""
Grip command-line interface.
"""

import argparse
import socket
import sys
import errno

from . import __version__
from .api import clear_cache, export, serve
from .exceptions import ReadmeNotFoundError

version = "Grip " + __version__

VALID_THEME_OPTIONS = ["light", "dark"]


def _split_address(address: str | None) -> tuple[str | None, int | None]:
    """Parse an address string into (host, port)."""
    if not address:
        return None, None
    if ":" in address:
        host, _, port_str = address.rpartition(":")
        host = host or None
        try:
            port = int(port_str)
        except ValueError:
            return address, None
        return host, port
    try:
        return None, int(address)
    except ValueError:
        return address, None


def _resolve_path_address(path_arg, address_arg):
    """Resolve positional arguments into (path, address)."""
    if path_arg is None or address_arg is not None:
        return path_arg, address_arg
    _, port = _split_address(path_arg)
    if port is not None:
        return None, path_arg
    return path_arg, None


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="grip",
        description="Render local readme files before sending off to GitHub.",
        add_help=True,
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="File or directory to render (- for stdin)",
    )
    parser.add_argument(
        "address",
        nargs="?",
        default=None,
        help="Host:port to listen on, or output file for --export",
    )
    parser.add_argument(
        "-V", action="store_true", default=False, help="Show version and exit"
    )
    parser.add_argument("--version", action="version", version=version)
    parser.add_argument("--user-content", action="store_true", default=False)
    parser.add_argument("--wide", action="store_true", default=False)
    parser.add_argument("--clear", action="store_true", default=False)
    parser.add_argument("--export", action="store_true", default=False)
    parser.add_argument("--no-inline", action="store_true", default=False)
    parser.add_argument("-b", "--browser", action="store_true", default=False)
    parser.add_argument("--title", default=None)
    parser.add_argument("--norefresh", action="store_true", default=False)
    parser.add_argument("--quiet", action="store_true", default=False)
    parser.add_argument("--theme", default=None)
    return parser


def main(argv=None):
    """The entry point of the application."""
    if argv is None:
        argv = sys.argv[1:]

    # Legacy flag errors
    if "-a" in argv or "--address" in argv:
        print("Use grip [options] <path> <address> instead of -a")
        print("See grip -h for details")
        return 2
    if "-p" in argv or "--port" in argv:
        print("Use grip [options] [<path>] [<hostname>:]<port> instead of -p")
        print("See grip -h for details")
        return 2

    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.V:
        print(version)
        return 0

    if args.clear:
        clear_cache()
        return 0

    # Theme
    if args.theme:
        if args.theme in VALID_THEME_OPTIONS:
            theme = args.theme
        else:
            print('Error: valid options for theme argument are "light", "dark"')
            return 1
    else:
        theme = "light"

    # Export
    if args.export:
        try:
            export(
                args.path,
                args.user_content,
                args.wide,
                not args.no_inline,
                args.address,
                args.title,
                args.quiet,
                theme,
            )
            return 0
        except ReadmeNotFoundError as ex:
            print("Error:", ex)
            return 1

    # Serve
    path, address = _resolve_path_address(args.path, args.address)
    host, port = _split_address(address)

    if address and not host and port is None:
        print("Error: Invalid address", repr(address))

    try:
        serve(
            path,
            host,
            port,
            args.user_content,
            args.wide,
            args.title,
            not args.norefresh,
            args.browser,
            args.quiet,
            theme,
        )
        return 0
    except ReadmeNotFoundError as ex:
        print("Error:", ex)
        return 1
    except socket.error as ex:
        print("Error:", ex)
        if ex.errno == errno.EADDRINUSE:
            print(
                "This port is in use. Is a grip server already running? "
                "Stop that instance or specify another port here."
            )
        return 1
