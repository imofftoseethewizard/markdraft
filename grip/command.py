"""\
grip.command
~~~~~~~~~~~~

Implements the command-line interface for Grip.


Usage:
  grip [options] [<path>] [<address>]
  grip -V | --version
  grip -h | --help

Where:
  <path> is a file to render or a directory containing README.md (- for stdin)
  <address> is what to listen on, of the form <host>[:<port>], or just <port>

Options:
  --user-content    Render as user-content like comments or issues.
  --context=<repo>  The repository context, only taken into account
                    when using --user-content.
  --user=<username> A GitHub username for API authentication. If used
                    without the --pass option, an upcoming password
                    input will be necessary.
  --pass=<password> A GitHub password or auth token for API auth.
  --wide            Renders wide, i.e. when the side nav is collapsed.
                    This only takes effect when --user-content is used.
  --clear           Clears the cached styles and assets and exits.
  --export          Exports to <path>.html or README.md instead of
                    serving, optionally using [<address>] as the out
                    file (- for stdout).
  --no-inline       Link to styles instead inlining when using --export.
  -b --browser      Open a tab in the browser after the server starts.
  --api-url=<url>   Specify a different base URL for the github API,
                    for example that of a Github Enterprise instance.
                    Default is the public API: https://api.github.com
  --title=<title>   Manually sets the page's title.
                    The default is the filename.
  --norefresh       Do not automatically refresh the Readme content when
                    the file changes.
  --quiet           Do not print to the terminal.
  --theme=<theme>   Theme to view markdown file (light mode or dark mode).
                    Valid options ("light", "dark"). Default: "light"
"""

import argparse
import sys
import mimetypes
import socket
import errno

from getpass import getpass

from . import __version__
from .api import clear_cache, export, serve
from .exceptions import ReadmeNotFoundError


version = 'Grip ' + __version__

# Note: GitHub supports more than light mode and dark mode (exp: light-high-constrast, dark-high-constrast).
VALID_THEME_OPTIONS = ['light', 'dark']


def _split_address(address):
    """Parse an address string into (host, port).

    Accepts 'host:port', ':port', 'host', or a bare port number.
    Returns (host_or_None, port_as_int_or_None).
    """
    if not address:
        return None, None

    if ':' in address:
        host, _, port_str = address.rpartition(':')
        host = host or None
        try:
            port = int(port_str)
        except ValueError:
            return address, None
        return host, port

    # Bare token: if it's a number, treat as port; otherwise as host
    try:
        return None, int(address)
    except ValueError:
        return address, None


def _resolve_path_address(path_arg, address_arg):
    """Resolve positional arguments into (path, address).

    When only one positional is given, determine whether it's a path or
    an address based on whether it parses as a port number or host:port.
    """
    if path_arg is None or address_arg is not None:
        return path_arg, address_arg

    # Single positional: is it an address?
    _, port = _split_address(path_arg)
    if port is not None:
        return None, path_arg

    return path_arg, None


def _build_parser():
    parser = argparse.ArgumentParser(
        prog='grip',
        description='Render local readme files before sending off to GitHub.',
        add_help=True)
    parser.add_argument('path', nargs='?', default=None,
                        help='File or directory to render (- for stdin)')
    parser.add_argument('address', nargs='?', default=None,
                        help='Host:port to listen on, or output file for --export')
    parser.add_argument('-V', action='store_true', default=False,
                        help='Show version and exit')
    parser.add_argument('--version', action='version', version=version)
    parser.add_argument('--user-content', action='store_true', default=False)
    parser.add_argument('--context', default=None)
    parser.add_argument('--user', default=None)
    parser.add_argument('--pass', dest='password', default=None)
    parser.add_argument('--wide', action='store_true', default=False)
    parser.add_argument('--clear', action='store_true', default=False)
    parser.add_argument('--export', action='store_true', default=False)
    parser.add_argument('--no-inline', action='store_true', default=False)
    parser.add_argument('-b', '--browser', action='store_true', default=False)
    parser.add_argument('--api-url', default=None)
    parser.add_argument('--title', default=None)
    parser.add_argument('--norefresh', action='store_true', default=False)
    parser.add_argument('--quiet', action='store_true', default=False)
    parser.add_argument('--theme', default=None)
    return parser


def main(argv=None):
    """
    The entry point of the application.
    """
    if argv is None:
        argv = sys.argv[1:]

    # Show specific errors for legacy flags
    if '-a' in argv or '--address' in argv:
        print('Use grip [options] <path> <address> instead of -a')
        print('See grip -h for details')
        return 2
    if '-p' in argv or '--port' in argv:
        print('Use grip [options] [<path>] [<hostname>:]<port> instead of -p')
        print('See grip -h for details')
        return 2

    parser = _build_parser()
    args = parser.parse_args(argv)

    # Handle printing version with -V
    if args.V:
        print(version)
        return 0

    # Clear the cache
    if args.clear:
        clear_cache()
        return 0

    # Get password from prompt if necessary
    password = args.password
    if args.user and not password:
        password = getpass()

    # Parse theme argument
    if args.theme:
        if args.theme in VALID_THEME_OPTIONS:
            theme = args.theme
        else:
            print('Error: valid options for theme argument are "light", "dark"')
            return 1
    else:
        theme = 'light'

    # Export to a file instead of running a server
    if args.export:
        try:
            export(args.path, args.user_content, args.context,
                   args.user, password, False, args.wide,
                   not args.no_inline, args.address,
                   args.api_url, args.title, args.quiet, theme)
            return 0
        except ReadmeNotFoundError as ex:
            print('Error:', ex)
            return 1

    # Parse positional arguments
    path, address = _resolve_path_address(args.path, args.address)
    host, port = _split_address(address)

    # Validate address
    if address and not host and port is None:
        print('Error: Invalid address', repr(address))

    # Run server
    try:
        serve(path, host, port, args.user_content, args.context,
              args.user, password, False, args.wide, False,
              args.api_url, args.title, not args.norefresh,
              args.browser, args.quiet, theme, None)
        return 0
    except ReadmeNotFoundError as ex:
        print('Error:', ex)
        return 1
    except socket.error as ex:
        print('Error:', ex)
        if ex.errno == errno.EADDRINUSE:
            print('This port is in use. Is a grip server already running? '
                  'Stop that instance or specify another port here.')
        return 1
