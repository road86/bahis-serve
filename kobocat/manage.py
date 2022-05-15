#!/usr/bin/env python
# encoding=utf-8
from __future__ import print_function
import logging
import os
import sys

from django.conf import settings

south_logger = logging.getLogger('south')
south_logger.setLevel(logging.INFO)



if __name__ == "__main__":
    # altered for new settings layout
    print (settings.MONGO_DATABASE)
    if not any([arg.startswith('--settings=') for arg in sys.argv]):
        os.environ.setdefault("DJANGO_SETTINGS_MODULE",
                              "onadata.settings.common")
        print('Your environment is:"{}"'.format(
            os.environ['DJANGO_SETTINGS_MODULE']))

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
