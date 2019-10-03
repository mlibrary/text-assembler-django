"""
Helper class to determine the location to save files. This was created
to help prevent a flat structure which is inefficient for searches larger
than 10,000 results.

This structure will be in the form:
[Search ID]/1/1/1
...
[Search ID]/1/1/[Max Number of Sub Dirs]
...
[Search ID]/1/[Max Number of Sub Dirs]/1
...
[Search ID]/1/[Max Number of Sub Dirs]/[Max Number of Sub Dirs]
...
[Search ID]/2/1/1
...
...

Determining which directory to use will be based off of the Max Number of
Files per Dir setting.

The parent directory under the Search ID will not be limited by the number
of sub directories because then we would end up having caps to the number
of results we could handle. But ideally, you would want this to remain
under the max number of sub directories settings as well.

The maximum number of files/sub-directories per directory before it
starts to become an efficiency issue is 10,000. So you should take that
into consideration when setting those configurations.
"""
import os
#import logging
from django.conf import settings


def get_path(cur_path):
    '''
    Get the save location for the next result file
    given the current path being used.
    Returns:
        new_path (string): New save location to use
    '''

    # Check if the current path is the base path, i.e. this is a new search
    #logging.debug(f"{os.path.dirname(cur_path)} == {settings.STORAGE_LOCATION}")
    if os.path.dirname(cur_path) == settings.STORAGE_LOCATION:
        new_path = os.path.join(cur_path, "1/1/1")
        if not os.path.exists(new_path):
            os.makedirs(new_path)
        return new_path

    # See if the current directory can handle more files
    ## Get the 1st directory in that path (i.e. HTML, TXT, TXT_Only)
    for cur_path_dirs in os.listdir(cur_path):
        if os.path.isdir(os.path.join(cur_path, cur_path_dirs)):
            format_dir = os.path.join(cur_path, cur_path_dirs)
            break
    ## Check the number of files in the format dir
    #logging.debug(f"Files in format_dir ({format_dir}): {len(os.listdir(format_dir))}")
    if len(os.listdir(format_dir)) < settings.MAX_FILES_PER_DIR:
        return cur_path

    # See if the parent directory can handle more sub directories
    parent_dir = os.path.dirname(cur_path) # go up one level
    num_dirs_in_dir = len(os.listdir(parent_dir))
    #logging.debug(f"Dirs in parent_dir ({parent_dir}): {num_dirs_in_dir}")
    if num_dirs_in_dir < settings.MAX_SUB_DIRS_PER_DIR:
        new_folder = num_dirs_in_dir + 1 # increment the last dir number used
        new_path = os.path.join(parent_dir, str(new_folder))
        #logging.debug(f"New path: {new_path}")
        if not os.path.exists(new_path):
            os.makedirs(new_path)
        return new_path

    # See if the grand-parent directory can handle more sub directories
    gparent_dir = os.path.dirname(parent_dir)
    num_dirs_in_dir = len(os.listdir(gparent_dir))
    #logging.debug(f"Dirs in gparent_dir ({gparent_dir}): {num_dirs_in_dir}")
    if num_dirs_in_dir < settings.MAX_SUB_DIRS_PER_DIR:
        new_parent_dir = num_dirs_in_dir + 1 # increment the last dir number used
        new_path = os.path.join(gparent_dir, str(new_parent_dir) + "/1")
        #logging.debug(f"New path: {new_path}")
        if not os.path.exists(new_path):
            os.makedirs(new_path)
        return new_path

    # Last resort, create a new sub-directory in the base level
    base_dir = os.path.dirname(gparent_dir)
    num_dirs_in_dir = len(os.listdir(base_dir))  # num in /[Search ID]/
    #logging.debug(f"Dirs in ggparent_dir ({base_dir}): {num_dirs_in_dir}")
    new_ggparent_dir = os.path.join(base_dir, str(num_dirs_in_dir + 1))  # /[Search ID]/X
    new_path = os.path.join(new_ggparent_dir, "1/1")
    #logging.debug(f"New path: {new_path}")
    if not os.path.exists(new_path):
        os.makedirs(new_path)
    return new_path
