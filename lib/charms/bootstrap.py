import os
import platform
import sys
import shutil
from glob import glob
from subprocess import check_call

class DistributionNotSupported(Exception):
    pass

def bootstrap_charm_deps():
    """
    Set up the base charm dependencies so that the reactive system can run.
    """
    venv = os.path.abspath('../.venv')
    vbin = os.path.join(venv, 'bin')
    vpip = os.path.join(vbin, 'pip')
    vpy = os.path.join(vbin, 'python')
    if os.path.exists('wheelhouse/.bootstrapped'):
        from charms import layer
        cfg = layer.options('basic')
        if cfg.get('use_venv') and '.venv' not in sys.executable:
            # activate the venv
            os.environ['PATH'] = ':'.join([vbin, os.environ['PATH']])
            reload_interpreter(vpy)
        return
    # bootstrap wheelhouse
    if os.path.exists('wheelhouse'):
        wheelhouse_setup_packages()
        from charms import layer
        cfg = layer.options('basic')
        # include packages defined in layer.yaml
        package_install(cfg.get('packages', []))
        # if we're using a venv, set it up
        if cfg.get('use_venv'):
            setup_venv()
            cmd = ['virtualenv', '--python=python3', venv]
            if cfg.get('include_system_packages'):
                cmd.append('--system-site-packages')
            check_call(cmd)
            os.environ['PATH'] = ':'.join([vbin, os.environ['PATH']])
            pip = vpip
        else:
            pip = 'pip3'
            # save a copy of system pip to prevent `pip3 install -U pip` from changing it
            if os.path.exists('/usr/bin/pip'):
                shutil.copy2('/usr/bin/pip', '/usr/bin/pip.save')
        # need newer pip, to fix spurious Double Requirement error https://github.com/pypa/pip/issues/56
        check_call([pip, 'install', '-U', '--no-index', '-f', 'wheelhouse', 'pip'])
        # install the rest of the wheelhouse deps
        check_call([pip, 'install', '-U', '--no-index', '-f', 'wheelhouse'] + glob('wheelhouse/*'))
        if not cfg.get('use_venv'):
            # restore system pip to prevent `pip3 install -U pip` from changing it
            if os.path.exists('/usr/bin/pip.save'):
                shutil.copy2('/usr/bin/pip.save', '/usr/bin/pip')
                os.remove('/usr/bin/pip.save')
        # flag us as having already bootstrapped so we don't do it again
        open('wheelhouse/.bootstrapped', 'w').close()
        # Ensure that the newly bootstrapped libs are available.
        # Note: this only seems to be an issue with namespace packages.
        # Non-namespace-package libs (e.g., charmhelpers) are available
        # without having to reload the interpreter. :/
        reload_interpreter(vpy if cfg.get('use_venv') else sys.argv[0])


def reload_interpreter(python):
    """
    Reload the python interpreter to ensure that all deps are available.

    Newly installed modules in namespace packages sometimes seemt to
    not be picked up by Python 3.
    """
    os.execle(python, python, sys.argv[0], os.environ)

def package_install(packages):
    """
    Install apt/yum packages.

    This ensures a consistent set of options that are often missed but
    should really be set.
    """
    if not packages:
        return
    if isinstance(packages, (str, bytes)):
        packages = [packages]

    env = os.environ.copy()

    distro = get_distro()
    if "Ubuntu" in distro:
        if 'DEBIAN_FRONTEND' not in env:
            env['DEBIAN_FRONTEND'] = 'noninteractive'

        cmd = ['apt-get',
            '--option=Dpkg::Options::=--force-confold',
            '--assume-yes',
            'install']
    elif "CentOS" in distro:
        cmd = ['yum',
            '--assumeyes',
            '--debuglevel=1',
            'install']
    else:
        raise DistributionNotSupported

    check_call(cmd + packages, env=env)

def wheelhouse_setup_packages():
    distro = get_distro()
    if "Ubuntu" in distro:
        package_install(['python3-pip', 'python3-yaml'])
    if "CentOS" in distro:
        package_install(['python34-PyYAML'])
        env = os.environ.copy()
        check_call(['easy_install-3.4', 'pip'])
    else:
        raise DistributionNotSupported

def setup_venv():
    distro = get_distro()
    if "Ubuntu" in distro:
        package_install(['python-virtualenv'])
    if "CentOS" in distro:
        check_call(['pip3', 'install', 'virtualenv'])
    else:
        raise DistributionNotSupported

def get_distro():
    return platform.linux_distribution()[0]
