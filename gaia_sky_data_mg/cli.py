import sys
import argparse

from .config import load_config, Config
from .commands import (
    cmd_update, cmd_list, cmd_info, cmd_search,
    cmd_download, cmd_upgrade, cmd_remove,
)
from .exceptions import GaiaSkyDataError


def main():
    parser = argparse.ArgumentParser(
        prog='gaia-sky-data-mg',
        description='Gaia Sky dataset manager',
    )
    parser.add_argument('-c', '--config', help='Config file path')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--data-path', help='Override data path')
    parser.add_argument('--no-cache', action='store_true', help='Force fresh descriptor fetch')

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # update
    sub_update = subparsers.add_parser('update', help='Check for dataset updates')

    # list
    sub_list = subparsers.add_parser('list', help='List datasets')
    sub_list.add_argument('--available', action='store_true',
                          help='List all available remote datasets')

    # info
    sub_info = subparsers.add_parser('info', help='Show dataset details')
    sub_info.add_argument('package', help='Dataset key name')

    # search
    sub_search = subparsers.add_parser('search', help='Search datasets by keyword')
    sub_search.add_argument('keyword', help='Search keyword')

    # download
    sub_download = subparsers.add_parser('download', help='Download and extract a dataset')
    sub_download.add_argument('package', help='Dataset key name')

    # upgrade
    sub_upgrade = subparsers.add_parser('upgrade', help='Upgrade datasets')
    sub_upgrade.add_argument('package', nargs='?', default=None, help='Dataset key name')
    sub_upgrade.add_argument('--all', action='store_true',
                             help='Upgrade all outdated datasets')

    # remove
    sub_remove = subparsers.add_parser('remove', help='Remove an installed dataset')
    sub_remove.add_argument('package', help='Dataset key name')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 2

    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        return 1

    if args.data_path:
        config.data_path = args.data_path

    verbose = args.verbose

    try:
        dispatch = {
            'update': cmd_update,
            'list': cmd_list,
            'info': cmd_info,
            'search': cmd_search,
            'download': cmd_download,
            'upgrade': cmd_upgrade,
            'remove': cmd_remove,
        }

        handler = dispatch.get(args.command)
        if handler is None:
            print(f"Unknown command: {args.command}", file=sys.stderr)
            return 2

        return handler(config, args)

    except GaiaSkyDataError as e:
        print(f"Error: {e}", file=sys.stderr)
        if verbose:
            import traceback
            traceback.print_exc()
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main() or 0)
