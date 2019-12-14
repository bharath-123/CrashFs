'''
An In-Memory Filesystem with Crash Recovery.

Crash recovery is built keeping the Memento Design Pattern in mind
'''


from errno import *
from time import time
import sys
from os import getuid, getgid
from stat import *
from copy import copy, deepcopy

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn

class Data():
    def get_data(self):
        pass

    def set_data(self):
        pass

class FileData(Data):
    '''
    File data is just stored as string
    '''
    def __init__(self):
        self.data = ""

    def get_data(self):
        return self.data

    # truncate not supported
    def set_data(self, new_data):
        self.data = new_data

    def get_size(self):
        return len(self.data)

class SymlinkData(Data):
    '''
    Symlink data is just stored as filename.
    '''
    def __init__(self):
        self.file = ""
        
    def get_data(self):
        return self.file

    def set_data(self, new_file):
        self.file = new_file

    def get_size(self):
        return len(self.data)

class DirData(Data):
    '''
    Directory data is just the inode list 
    which we maintain in each inode. But add a
    class just so that we can add more functionality
    in the future
    '''
    # can be extended to add more features
    def get_size(self):
        return 4096

class Inode():
    def __init__(self, create_inode, name, mode=None, 
            ctime=None, atime=None, mtime=None,
            uid=None, gid=None):
        self.name = name
        self.inodes = [] # list of inodes in that directory
        if create_inode:
            self.inode = _Inode(
                mode, 
                ctime, 
                atime,
                mtime,
                uid,
                gid
                )

    def set_inode(self, new_inode):
        self.inode = new_inode

    def get_inode(self):
        return self.inode

    def set_name(self, new_name):
        self.name = new_name
        
    def set_ctime(self, ctime):
        if self.inode:
            self.inode.ctime = ctime

    def set_atime(self, atime):
        if self.inode:
            self.inode.atime = atime

    def set_mtime(self, mtime):
        if self.inode:
            self.inode.mtime = mtime

    # used to set permission bits
    def set_mode(self, mode):    
        if self.inode:
            self.inode.mode &= 0o770000
            self.inode.mode |= mode

    def set_uid(self, uid):
        if self.inode:
            self.inode.uid = uid

    def set_gid(self, gid):
        if self.inode:
            self.inode.gid = gid

    def get_inode_info(self):
        if self.inode:
            return self.inode.get_inode_info()

    def get_inode_type(self):
        if self.inode:
            return S_IFMT(self.inode.mode)

    def get_data(self):
        if self.inode:
            return self.inode.get_data()

    def set_data(self, new_data):
        if self.inode:
            return self.inode.set_data(new_data)

    def get_nlink(self):
        if self.inode:
            return self.inode.nlink

    def dec_nlink(self):
        if self.inode:
            self.inode.nlink -= 1

    def inc_nlink(self):
        if self.inode:
            self.inode.nlink += 1

class _Inode():
    inode_cnt = 100

    def __init__(self, mode, ctime, atime,
            mtime, uid, gid):
        self.inode_no = _Inode.inode_cnt + 1
        self.mode = mode
        self.ctime = ctime
        self.atime = atime
        self.mtime = mtime
        self.uid = uid
        self.gid = gid
        self.data_blocks = self.get_data_class()
        if S_IFMT(self.mode) in [S_IFREG, S_IFLNK]:
            self.nlink = 1
        elif S_IFMT(self.mode) == S_IFDIR:
            self.nlink = 2

    def get_data_class(self):
        # no data stored for directory.
        # the inode list is enough data for the directory
        if S_IFMT(self.mode) == S_IFREG:
            return FileData()
        elif S_IFMT(self.mode) == S_IFLNK:
            return SymlinkData()
        elif S_IFMT(self.mode) == S_IFDIR:
            return DirData()

    def get_data(self):
        return self.data_blocks.get_data()

    def set_data(self, new_data):
        self.data_blocks.set_data(new_data)

    def get_size(self):
        return self.data_blocks.get_size()

    '''
    This is for the getattrs
    '''
    def get_inode_info(self):
        return dict(
            st_ino = self.inode_no,
            st_mode = self.mode,
            st_ctime = self.ctime,
            st_atime = self.atime,
            st_mtime = self.mtime,
            st_nlink = self.nlink,
            st_size = self.get_size(),
            st_uid = self.uid,
            st_gid = self.gid,
            st_blocks = int(self.get_size() / 512) + 1
        )

class CrashHistory():
    def __init__(self):
        self.history = None

    def add_to_history(self, state):
        self.history = state

    def get_latest_history(self):
        if self.history:
            return self.history

class MyFs(Operations):
    fs_name = "Myfs"
    
    def __init__(self):
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
        self.crash_history = CrashHistory()
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

    def chmod(self, path, mode):
        inode = self.get_inode(path, [S_IFDIR, S_IFREG, S_IFLNK])
        if inode is None:
            raise FuseOSError(ENOENT)

        inode.set_mode(mode)

    def chown(self, path, uid, gid):
        inode = self.get_inode(path, [S_IFDIR, S_IFREG, S_IFLNK])
        if inode is None:
            raise FuseOSError(ENOENT)

        inode.set_uid(uid)
        inode.set_gid(gid)

    # need to implement to overwrite files
    # Increase the size of the file
    def truncate(self, path, length):
        pass

    def write(self, path, data, offset, fh):
        # intercept write to the restore and store files
        if path in ("/restore", "/store"):
            self.handle_fs_state(path)
            return 1
        
        inode = self.get_inode(path, [S_IFREG, S_IFLNK])        
        if inode is None:
            raise FuseOSError(ENOENT)

        inode.set_data(data) 

        return len(data)

    def read(self, path, size, offset, fh):
        inode = self.get_inode(path, [S_IFREG, S_IFLNK])
        if inode is None:
            raise FuseOSError(ENOENT)

        return inode.get_data()

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

    def rename(self, old, new):
        curr_inode = self.get_inode(old, [S_IFREG, S_IFDIR])
        if curr_inode is None:
            raise FuseOSError(ENOENT)

        new_filename, parent_dir = MyFs.get_filename_and_parentdir(new)
        curr_inode.set_name(new_filename)

        self.invalidate_cache(old)

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

    def readlink(self, path):
        link_inode = self.get_inode(path, [S_IFLNK])
        if link_inode is None:
            raise FuseOSError(ENOENT)

        return link_inode.get_data()

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
   
    def rmdir(self, path): 
        curr_filename, parent_dir = MyFs.get_filename_and_parentdir(path)

        curr_inode = self.get_inode(path, [S_IFDIR])
        parent_inode = self.get_inode(parent_dir, [S_IFDIR])
        if (parent_inode is None) or (curr_inode is None):
            raise FuseOSError(ENOENT)

        parent_inode.inodes.remove(curr_inode)

        del curr_inode

        self.invalidate_cache(path)

    def readdir(self, path, fh):  
        node = self.get_inode(path, [S_IFDIR, S_IFREG, S_IFLNK])
        if node is None:
            return None

        for node in node.inodes:
            yield node.name

    def getattr(self, path, fh=None):
        node = self.get_inode(path, [S_IFDIR, S_IFREG, S_IFLNK])
        if node is None:
            raise FuseOSError(ENOENT)
        
        return node.get_inode_info()
        
if __name__ == "__main__":
    mount_point = sys.argv[1]

    fuse = FUSE(MyFs(), mount_point, foreground=True, nothreads=True)

