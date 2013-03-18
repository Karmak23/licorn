# -*- coding: utf-8 -*-
"""
Licorn Foundations: base settings - http://docs.licorn.org/foundations/

Copyright (C) 2011 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2
"""


# ================================================= Licorn® foundations imports

from base      import ObjectSingleton, LicornConfigObject
from constants import distros

LMC = None


class LicornPlatform(ObjectSingleton, LicornConfigObject):
    def __init__(self, filename=None):

        # ôô my hack!!
        global LMC
        from licorn.core import LMC as licorn_lmc
        LMC = licorn_lmc

    @property
    def is_debian_derivative(self):
        return LMC.configuration.distro in (distros.LICORN,
                                            distros.UBUNTU,
                                            distros.DEBIAN)


platform = LicornPlatform()

__all__ = ('platform', )
