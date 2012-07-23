#!/usr/bin/python
# taken from /usr/lib/update-notifier/apt_check.py in Ubuntu Oneiric, replicated
# to avoid the need for installing update-notifier, and to have the functionnality
# on debian, too.

#nice apt-get -s -o Debug::NoLocking=true upgrade | grep ^Inst

import sys, os, apt_pkg, subprocess

from licorn.foundations import logging
from licorn.core        import LMC

SYNAPTIC_PINFILE = "/var/lib/synaptic/preferences"
DISTRO = subprocess.Popen(["lsb_release","-c","-s"],
                          stdout=subprocess.PIPE).communicate()[0].strip()

class OpNullProgress(object):
    def update(self, percent):
        pass
    def done(self):
        pass

def _handleException(type, value, tb):
    sys.stderr.write("E: "+ _("Unknown Error: '{0}' ({1})").format(type,value))
    sys.exit(-1)

def clean(cache, depcache):
    " unmark (clean) all changes from the given depcache "
    # mvo: looping is too inefficient with the new auto-mark code
    #for pkg in cache.Packages:
    #    depcache.MarkKeep(pkg)
    depcache.init()

def saveDistUpgrade(cache, depcache):
    """ this functions mimics a upgrade but will never remove anything """
    depcache.upgrade(True)
    if depcache.del_count > 0:
        clean(cache,depcache)
    depcache.upgrade()

def isSecurityUpgrade(ver):
    " check if the given version is a security update (or masks one) "
    security_pockets = [("Ubuntu", "%s-security" % DISTRO),
                        ("gNewSense", "%s-security" % DISTRO),
                        ("Debian", "%s-updates" % DISTRO)]

    for (file, index) in ver.file_list:
        for origin, archive in security_pockets:
            if (file.archive == archive and file.origin == origin):
                return True
    return False

def write_package_names(outstream, cache, depcache):
    " write out package names that change to outstream "
    pkgs = filter(lambda pkg:
                  depcache.marked_install(pkg) or depcache.marked_upgrade(pkg),
                  cache.packages)
    outstream.write("\n".join(map(lambda p: p.name, pkgs)))


def init():
    " init the system, be nice "
    # FIXME: do a ionice here too?
    #os.nice(19)

    # this should have been done in foundations.
    #apt_pkg.init()

    # force apt to build its caches in memory for now to make sure
    # that there is no race when the pkgcache file gets re-generated
    apt_pkg.config.set("Dir::Cache::pkgcache","")

def run(options=None):

    # we are run in "are security updates installed automatically?"
    # question mode
    if options.security_updates_unattended:
        return apt_pkg.config.find_i("APT::Periodic::Unattended-Upgrade", 0)

    # get caches
    cache = apt_pkg.Cache(OpNullProgress())
    depcache = apt_pkg.DepCache(cache)

    # read the pin files
    depcache.read_pinfile()

    # read the synaptic pins too
    if os.path.exists(SYNAPTIC_PINFILE):
        depcache.read_pinfile(SYNAPTIC_PINFILE)

    # init the depcache
    depcache.init()

    if depcache.broken_count > 0:
        raise RuntimeError(_("Error: BrokenCount > 0"))

    saveDistUpgrade(cache,depcache)

    # analyze the ugprade
    upgrades = 0
    security_updates = 0
    for pkg in cache.packages:
        # skip packages that are not marked upgraded/installed
        if not (depcache.marked_install(pkg) or depcache.marked_upgrade(pkg)):
            continue
        # check if this is really a upgrade or a false positive
        # (workaround for ubuntu #7907)
        inst_ver = pkg.current_ver
        cand_ver = depcache.get_candidate_ver(pkg)
        if cand_ver == inst_ver:
            continue

        # check for security upgrades
        upgrades += 1
        if isSecurityUpgrade(cand_ver):
            security_updates += 1
            continue

        # now check for security updates that are masked by a
        # canidate version from another repo (-proposed or -updates)
        for ver in pkg.version_list:
            if (inst_ver and apt_pkg.version_compare(ver.ver_str, inst_ver.ver_str) <= 0):
                #print "skipping '%s' " % ver.VerStr
                continue
            if isSecurityUpgrade(ver):
                security_updates += 1
                break

    if options.show_package_names:
        return (cache, depcache)

    return(upgrades, security_updates)

