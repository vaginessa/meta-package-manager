#!/usr/bin/env python
# -*- coding: utf-8 -*-
# <bitbar.title>Meta Package Manager</bitbar.title>
# <bitbar.version>v1.12.1</bitbar.version>
# <bitbar.author>Kevin Deldycke</bitbar.author>
# <bitbar.author.github>kdeldycke</bitbar.author.github>
# <bitbar.desc>List outdated packages on system and allow upgrades.</bitbar.desc>
# <bitbar.dependencies>python</bitbar.dependencies>
# <bitbar.image>https://i.imgur.com/CiQpQ42.png</bitbar.image>
# <bitbar.abouturl>https://github.com/kdeldycke/meta-package-manager</bitbar.abouturl>

"""
Default update cycle is set to 7 hours so we have a chance to get user's
attention once a day. Higher frequency might ruin the system as all checks are
quite resource intensive, and Homebrew might hit GitHub's API calls quota.
"""

from __future__ import print_function, unicode_literals

import json
from operator import itemgetter
from subprocess import PIPE, CalledProcessError, Popen, check_call


def mpm_available():
    """ Search for generic mpm CLI on system. """
    try:
        # Do not reprint CLI output on screen but errors.
        check_call(['mpm'], stdout=PIPE)
    except (CalledProcessError, OSError):
        return False
    return True


def print_error_header():
    """ Generic header for blockng error. """
    print("❌ | dropdown=false".encode('utf-8'))
    print("---")


def print_error(message):
    """ Print a formatted error line by line, in red. """
    for line in message.strip().split("\n"):
        print("{} | color=red font=Menlo".format(line))


def print_menu():
    """ Print menu structure using BitBar's plugin API.

    See: https://github.com/matryer/bitbar#plugin-api
    """
    # Check availability of mpm.
    if not mpm_available():
        # mpm can't be found. Stop right away and propose to install it.
        print_error_header()
        print(
            "`mpm` CLI not found. Click here to install. | bash=pip "
            "param1=install param2=--upgrade param3=meta-package-manager "
            "terminal=true refresh=true color=red")
        return

    # Fetch list of all outdated packages from all package manager available on
    # the system.
    process = Popen([
        'mpm', '--output-format', 'json', 'outdated', '--cli-format',
        'bitbar'], stdout=PIPE, stderr=PIPE)
    output, error = process.communicate()

    if error:
        print_error_header()
        print_error(error)
        return

    # Sort outdated packages by manager's name.
    managers = sorted(
        json.loads(output.decode('utf-8')).values(),
        key=itemgetter('name'))

    # Print menu bar icon with number of available upgrades.
    total_outdated = sum([len(m['packages']) for m in managers])
    total_errors = len([True for m in managers if m['error']])
    print(("↑{}{} | dropdown=false".format(
        total_outdated,
        " ⚠️{}".format(total_errors) if total_errors else ""
    )).encode('utf-8'))

    # Print a full detailed section for each manager.
    for manager in managers:
        print("---")

        if manager['error']:
            print_error(manager['error'])

        print("{} outdated {} package{}".format(
            len(manager['packages']),
            manager['name'],
            's' if len(manager['packages']) != 1 else ''))

        # TODO: Re-implement full upgrade.
        # if manager.upgrade_all_cli() and manager.outdated:
        #     print("Upgrade all | {} terminal=false refresh=true".format(
        #         manager.upgrade_all_cli()))

        for pkg_info in manager['packages']:
            print((
                "{name} {installed_version} → {latest_version} | "
                "{upgrade_cli} terminal=false refresh=true".format(
                    **pkg_info)).encode('utf-8'))


if __name__ == '__main__':
    print_menu()
