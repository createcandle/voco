"""
This script exists to ensure that required dependencies are present.

To prevent the need for building dependencies for every possible OS/arch/Python
combination, this script will build the required dependencies. After doing so,
or if the dependencies are already present, main.py will be started.
"""

import os
import subprocess
import sys

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

print("")
print("")
print("HELLO THERE")
def install_packages():
    """Install all packages listed in requirements.txt."""
    system_option = ''
    try:
        import lsb_release
        print("lsb_release.get_distro_information()['ID'] = " + str(lsb_release.get_distro_information()['ID']))
        if lsb_release.get_distro_information()['ID'] in ['Raspbian',
                                                          'Debian']:
            system_option = '--system'
    except ImportError:
        print("unable to determine your linux distribution. Will try to continue.")
        pass

    #cmd = (
    #    '{} -m pip install {} --install-option="--prefix=" -t lib '
    #    '-r requirements.txt'.format(sys.executable, system_option))

    
    cmd = 'pip3 install -r requirements.txt -t lib --no-binary fuzzywuzzy --prefix ""'
    #cmd = (
    #    '{} -m pip install --install-option="--prefix=" -t lib '
    #    '-r requirements.txt'.format(sys.executable))
    
    
    print("Command that will install the dependencies: " + str(cmd))
    try:
        subprocess.check_call(cmd,
                              stderr=subprocess.STDOUT,
                              shell=True,
                              cwd=_BASE_DIR)
        return True
    except subprocess.CalledProcessError as e:
        print("Unable to install dependencies: " + str(e))
        return False


try:
    print("_BASE_DIR = " + str(_BASE_DIR))
    sys.path.append(os.path.join(_BASE_DIR, 'lib'))

    #from hermes_python.hermes import Hermes # noqa: F401
    #from hermes_python.ontology import * # noqa: F401
    import hermes_python  # noqa: F401
    import fuzzywuzzy  # noqa: F401
    import pyalsaaudio  # noqa: F401
except ImportError as ex:
    print("Import error: " + str(ex))
    # If installation failed, exit with 100 to tell the gateway not to restart
    # this process.
    if not install_packages():
        sys.exit(100)

os.execl(sys.executable, sys.executable, os.path.join(_BASE_DIR, 'main.py'))