# Copyright Kevin Deldycke <kevin@deldycke.com> and contributors.
# All Rights Reserved.
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

""" Registration, indexing and caching of package manager definitions. """

import inspect
from functools import cached_property
from importlib import import_module
from pathlib import Path

from boltons.cacheutils import LRI, cached
from boltons.iterutils import unique

from . import logger
from .base import PackageManager


class ManagerPool:

    ALLOWED_EXTRA_OPTION = frozenset({"ignore_auto_updates", "stop_on_error", "dry_run"})
    """List of extra options that are allowed to be set on managers during the use of the
    :py:func:`meta_package_manager.managers.select_managers` helper below."""

    manager_subfolder = "managers"
    """Relative subfolder where to search for manager definition files."""

    # Cache of the global pool of registered manager definitions.
    #register = {}

    @cached_property
    def pool(self):
        """Search for package manager definitions locally and store them into an
        internal register.

        Is considered valid package manager, definitions classes which:
            1 - are located in the `managers` subfolder, and
            2 - are sub-classes of PackageManager, and
            3 - are not virtual (i.e. have a non null `cli_names` property).
        """
        # Register has already been populated, return it.
        #if self.register:
        #    return self.register

        register = {}

        # Populate empty register.
        for py_file in Path(__file__).parent.joinpath(self.manager_subfolder).glob("*.py"):
            logger.debug(f"Search manager definitions in {py_file}")
            module = import_module(
                f".{self.manager_subfolder}.{py_file.stem}", package=__package__
            )

            for _, klass in inspect.getmembers(module, inspect.isclass):
                if issubclass(klass, PackageManager) and not klass.virtual:
                    logger.debug(f"Found {klass!r}")
                    manager = klass()
                    register[manager.id] = manager
                else:
                    logger.debug(f"{klass!r} is not a valid manager definition")

        return register


    # Emulates some dict methods.

    def __len__(self):
        return len(self.pool)

    def __getitem__(self, key):
        return self.pool[key]

    def __iter__(self):
        for key in self.pool:
            yield key

    def __contains__(self, key):
        return key in self.pool

    def values(self):
        return self.pool.values()

    def items(self):
        return self.pool.items()


    # Pre-compute all sorts of constants.

    @cached_property
    def all_manager_ids(self):
        """ All recognized manager IDs.

        Is a list of sorted items to provide consistency across all UI, and reproducability in
        the order package managers are evaluated.
        """
        return tuple(sorted(self.pool))

    @cached_property
    def default_manager_ids(self):
        """ All manager IDs supported on the current platform.

        Must keep the same order defined by ALL_MANAGER_IDS.
        """
        return tuple(mid for mid in self.all_manager_ids if self.pool[mid].supported)

    @cached_property
    def unsupported_manager_ids(self):
        """ All manager IDs unsupported on the current platform.

        Order is not important here as this list will be used to discard managers from selection
        sets.
        """
        return tuple((
            mid for mid in self.all_manager_ids if mid not in self.default_manager_ids
        ))

    def select_managers(
        self,
        keep=None,
        drop=None,
        drop_unsupported=True,
        drop_inactive=True,
        # implements=None,
        **extra_options,
    ):
        """Utility method to extract a subset of the manager pool based on selection list
        (`keep` parameter) and exclusion list (`drop` parameter) criterion.

        By default, all managers supported on the current platform are selected. Unless
        `drop_unsupported` is set to False, in which case all managers implemented by mpm
        are selected, regardless of their supported platform.

        `drop_inactive` filters out managers that where not found on the system.

        XXX Pre-filtering out manager which doesn't implements some property can be done with
        XXX the `implements` parameter.

        Finally, `extra_options` parameters are fed to the manager objects from the pool to
        set some options.

        Returns a generator producing a manager object one after the other.
        """
        if not keep:
            keep = self.default_manager_ids if drop_unsupported else self.all_manager_ids
        if not drop:
            drop = set()
        assert set(self.all_manager_ids).issuperset(keep)
        assert set(self.all_manager_ids).issuperset(drop)

        assert self.ALLOWED_EXTRA_OPTION.issuperset(extra_options)

        # Only keeps the subset selected by the user.
        selected_ids = keep

        # Deduplicate managers IDs while preserving order, then remove excluded managers.
        for manager_id in (mid for mid in unique(selected_ids) if mid not in drop):
            manager = self.pool[manager_id]

            # TODO: check if not implemeted before calling .available. It saves one call to the package manager CLI.

            # Filters out inactive managers.
            if drop_inactive and not manager.available:
                logger.warning(f"Skip unavailable {manager_id} manager.")
                continue

            # Apply manager-level options.
            for param, value in extra_options.items():
                assert hasattr(manager, param)
                setattr(manager, param, value)

            yield manager

pool = ManagerPool()

ALL_MANAGER_IDS = pool.all_manager_ids
DEFAULT_MANAGER_IDS = pool.default_manager_ids
UNSUPPORTED_MANAGER_IDS = pool.unsupported_manager_ids
