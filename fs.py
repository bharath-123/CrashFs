'''
An In-Memory Filesystem with Crash Recovery.

Crash recovery is built keeping the Memento Design Pattern in mind
'''


from errno import *
from time import time
import sys
from os import getuid, getgid, mkdir, path
from stat import *
from copy import copy, deepcopy
from data import *
from inode import *
from history import *
from decorators import *
import argparse
import pickle

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn

class MyFs(Operations):
    fs_name = "Myfs"
    
    def __init__(self, backupstore):
        self.root_inode = Inode(
            1,
            "/",
            S_IFDIR | 0o755,
            time(),
            time(),
            time(),
            getuid(),
            getgid()
            )
        self.crash_history = CrashHistory(backupstore)
        self.name2inode = {}
        self.fd = 0
        self.setup_pseudo_files()

    # setup files 'restore' and 'store' which 
    # restore the fs to the latest state and store
    # the current state of the fs in the crash_history object
    def setup_pseudo_files(self):
        restore = Inode(
                1, 
                "restore",
                S_IFREG | 0o755,
                time(),
                time(),
                time(),
                getuid(),
                getgid()
                )
        store = Inode(
                1,
                "store",
                S_IFREG | 0o755,
                time(),
                time(),
                time(),
                getuid(),
                getgid()
                )

        self.root_inode.inodes.append(restore)
        self.root_inode.inodes.append(store)

    def handle_fs_state(self, path):
        if path == "/restore":
            latest_state = self.crash_history.get_latest_history()
            if latest_state:
                self.root_inode = deepcopy(latest_state)
                self.wipe_out_cache()
        else:
            self.crash_history.add_to_history(deepcopy(self.root_inode))

    @staticmethod
    def get_filename_and_parentdir(path):
        path_list = path.split('/')
        # need to extract the current filename and parent_dirname
        # I think there may be a more idiomatic way to do this
        curr_filename = path_list[-1]
        parent_dir = '/'.join(path_list[:len(path_list) - 1])

        return curr_filename, parent_dir
    
    # we didnt cache the filename2inode mapping.
    # Search in the filesystem hierarchy. 
    # really expensive tho :(
    def search_root_inode(self, name, mode):
        # if name is just root inode...
        if name == '/':
            return self.root_inode
       
        # otherwise...
        # split the name upinto a list
        # much easier
    
        # bad at naming sorry
        name_list = name.split('/')
        name_list[0] = '/' # did this cuz it looks nice
        
        name_list_iter = iter(name_list) # who likes indexing anyways?
        next(name_list_iter) # skip the root inode
        # start at root inode
        temp_node = self.root_inode

        while True:
            found_node = False
            
            try:
                curr_name = next(name_list_iter)
            except StopIteration:
                return temp_node
            
            for node in temp_node.inodes:
                if ((node.name == curr_name) and (node.get_inode_type() in mode)):
                    temp_node = node
                    found_node = True
                    break

            if found_node == False:
                return None

    def get_inode(self, name, mode):
        # mode is the type of file we are searching for.
        # if we are searching for the parent dir, then we need 
        # to ignore files and links

        # we need to get the inode give the filename
        # first check the name2inode cache
        try:
            inode = self.name2inode[name]

        # oopsie inode not cached.
        # Need to search from the root_inode. bleh.
        except KeyError:
            inode = self.search_root_inode(name, mode)
            if inode is None:
                return None

            # now cache it
            self.name2inode[name] = inode

        return inode

    def wipe_out_cache(self):
        self.name2inode = {}

    def invalidate_cache(self, path):
        try:
            del self.name2inode[path]    
        except KeyError:
            pass
    
    @logger
    def chmod(self, path, mode):
        inode = self.get_inode(path, [S_IFDIR, S_IFREG, S_IFLNK])
        if inode is None:
            raise FuseOSError(ENOENT)

        inode.set_mode(mode)

    @logger
    def chown(self, path, uid, gid):
        inode = self.get_inode(path, [S_IFDIR, S_IFREG, S_IFLNK])
        if inode is None:
            raise FuseOSError(ENOENT)

        inode.set_uid(uid)
        inode.set_gid(gid)

    # need to implement to overwrite files
    # Increase the size of the file
    @logger
    def truncate(self, path, length):
        pass   

    @logger
    def write(self, path, data, offset, fh):
        # intercept write to the restore and store files
        if path in ("/restore", "/store"):
            self.handle_fs_state(path)
         
        inode = self.get_inode(path, [S_IFREG, S_IFLNK])        
        if inode is None:
            raise FuseOSError(ENOENT)

        inode.set_data(data) 

        return len(data)

    @logger
    def read(self, path, size, offset, fh):
        inode = self.get_inode(path, [S_IFREG, S_IFLNK])
        if inode is None:
            raise FuseOSError(ENOENT)

        return inode.get_data()

    @logger
    def link(self, dst, src):
        dst_filename, dst_parent_dir = MyFs.get_filename_and_parentdir(dst)
        src_filename, src_parent_dir = MyFs.get_filename_and_parentdir(src)
        
        src_inode = self.get_inode(src, [S_IFREG])
        dst_parent_inode = self.get_inode(dst_parent_dir, [S_IFDIR])
        if src_inode is None or dst_parent_inode is None:
            raise FuseOSError(ENONET)
        
        # first inc link count
        src_inode.inc_nlink()

        # don't like this. Need to figure out a way to not break 
        # other code tho
        dst_inode = Inode(0, dst_filename)

        dst_inode.set_inode(src_inode.get_inode())
        dst_parent_inode.inodes.append(dst_inode)

    @logger
    def unlink(self, path):
        curr_filename, parent_dir = MyFs.get_filename_and_parentdir(path)

        curr_inode = self.get_inode(path, [S_IFREG, S_IFLNK])
        parent_inode = self.get_inode(parent_dir, [S_IFDIR])
        if ((parent_inode is None) or (curr_inode is None)):
            raise FuseOSError(ENOENT)

        # first check the curr_inode link count
        # delete from parent inode only if link count is 0
        curr_inode.dec_nlink()
        
        parent_inode.inodes.remove(curr_inode)

        if curr_inode.get_nlink() == 0:
            del curr_inode

        self.invalidate_cache(path)

    @logger
    def rename(self, old, new):
        curr_inode = self.get_inode(old, [S_IFREG, S_IFDIR])
        if curr_inode is None:
            raise FuseOSError(ENOENT)

        new_filename, parent_dir = MyFs.get_filename_and_parentdir(new)
        curr_inode.set_name(new_filename)

        self.invalidate_cache(old)

    @logger
    def symlink(self, target, source): 
        target_filename, target_parent = MyFs.get_filename_and_parentdir(target)
        source_filename, source_parent = MyFs.get_filename_and_parentdir(target)

        target_parent_inode = self.get_inode(target_parent, [S_IFDIR])
        source_inode = self.get_inode(source, [S_IFREG, S_IFLNK])
        if target_parent_inode is None or source_inode is None:
            return 1

        target_inode = Inode(
                    1,
                    target_filename,
                    S_IFLNK | 0o777,
                    time(),
                    time(),
                    time(),
                    getuid(),
                    getgid()
                    )

        target_parent_inode.inodes.append(target_inode)
        target_inode.set_data(source)

        return 0

    @logger
    def readlink(self, path):
        link_inode = self.get_inode(path, [S_IFLNK])
        if link_inode is None:
            raise FuseOSError(ENOENT)

        return link_inode.get_data()

    @logger
    def create(self, path, mode): 
        curr_filename, parent_dir = MyFs.get_filename_and_parentdir(path)
        
        inode = Inode(
            1,
            curr_filename,
            S_IFREG | 0o755,
            time(),
            time(),
            time(),
            getuid(),
            getgid()
            )

        parent_inode = self.get_inode(parent_dir, [S_IFDIR])
        if parent_inode is None:
            raise FuseOSError(ENOENT)

        parent_inode.inodes.append(inode)

        return 0

    @logger
    def mkdir(self, path, mode):
        curr_filename, parent_dir = MyFs.get_filename_and_parentdir(path)
        
        inode = Inode(
            1,
            curr_filename,
            S_IFDIR | 0o755,
            time(),
            time(),
            time(),
            getuid(),
            getgid()
            )

        parent_inode = self.get_inode(parent_dir, [S_IFDIR])
        if parent_inode is None:
            raise FuseOSError(ENOENT)
        
        parent_inode.inodes.append(inode)

        return 0
   
    @logger
    def rmdir(self, path): 
        curr_filename, parent_dir = MyFs.get_filename_and_parentdir(path)

        curr_inode = self.get_inode(path, [S_IFDIR])
        parent_inode = self.get_inode(parent_dir, [S_IFDIR])
        if (parent_inode is None) or (curr_inode is None):
            raise FuseOSError(ENOENT)

        parent_inode.inodes.remove(curr_inode)

        del curr_inode

        self.invalidate_cache(path)
    
    @logger
    def readdir(self, path, fh):  
        node = self.get_inode(path, [S_IFDIR, S_IFREG, S_IFLNK])
        if node is None:
            return None

        for node in node.inodes:
            yield node.name

    @logger
    def getattr(self, path, fh=None):
        node = self.get_inode(path, [S_IFDIR, S_IFREG, S_IFLNK])
        if node is None:
            raise FuseOSError(ENOENT)
        
        return node.get_inode_info()
        
if __name__ == "__main__":
    fs_parser = argparse.ArgumentParser()

    fs_parser.add_argument('mountpoint', help="The mount point of this filesystem")
    fs_parser.add_argument('backupstore', help="The mount point of the backup filesystem(Preferably a different device)")

    args = fs_parser.parse_args()

    fuse = FUSE(MyFs(args.backupstore), args.mountpoint, foreground=True, nothreads=True)

