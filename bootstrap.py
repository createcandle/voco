"""
This script exists to ensure that required dependencies are present.

To prevent the need for building dependencies for every possible OS/arch/Python
combination, this script will build the required dependencies. After doing so,
or if the dependencies are already present, main.py will be started.
"""

import os
import subprocess
import sys
from snipskit.hermes.apps import HermesSnipsApp
from snipskit.hermes.decorators import intent


_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def install_packages():
    """Install all packages listed in requirements.txt."""
    system_option = ''
    try:
        import lsb_release
        if lsb_release.get_distro_information()['ID'] in ['Raspbian',
                                                          'Debian']:
            system_option = '--system'
    except ImportError:
        pass

    cmd = (
        '{} -m pip install {} --install-option="--prefix=" -t lib '
        '-r requirements.txt'.format(sys.executable, system_option))

    try:
        subprocess.check_call(cmd,
                              stderr=subprocess.STDOUT,
                              shell=True,
                              cwd=_BASE_DIR)
        return True
    except subprocess.CalledProcessError as e:
        print(e)
        return False


try:
    sys.path.append(os.path.join(_BASE_DIR, 'lib'))

    import snipskit  # noqa: F401
except ImportError:
    # If installation failed, exit with 100 to tell the gateway not to restart
    # this process.
    if not install_packages():
        sys.exit(100)

os.execl(sys.executable, sys.executable, os.path.join(_BASE_DIR, 'main.py'))
