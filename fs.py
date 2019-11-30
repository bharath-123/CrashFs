'''
An In-Memory Filesystem with Crash Recovery.

Crash recovery is built keeping the Memento Design Pattern in mind
'''


from errno import *
from time import time
import sys
from os import getuid, getgid
from stat import *

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn

class FileData():
    '''
    File data is just stored as string
    '''
    def __init__(self):
        self.data = ""

    def get_data(self):
        return self.data

    # currently no truncate support
    def add_data(self, new_data):
        self.data = new_data

class Inode():
    def __init__(self, mode, ctime, atime,
            mtime, uid, gid, name):
        self.mode = mode
        self.ctime = ctime
        self.atime = atime
        self.mtime = mtime
        self.uid = uid
        self.gid = gid
        self.name = name 
        self.data_blocks = self.get_data_class()
        self.inodes = [] # list of inodes in that directory
        if self.mode & S_IFREG:
            self.nlink = 1
        elif self.mode & S_IFDIR:
            self.nlink = 2

    def set_name(self, new_name):
        self.name = new_name

    def get_data_class(self):
        # no data stored for directory.
        # the inode list is enough data for the directory
        if (S_IFMT(self.mode) == S_IFREG):
            return FileData()

    def get_size(self):
        if (S_IFMT(self.mode) == S_IFREG):
            return len(self.data_blocks.get_data())
        elif (S_IFMT(self.mode) == S_IFDIR):
            return 4096

    '''
    This is for the getattrs
    '''
    def get_inode_info(self):
        return dict(
            st_mode = self.mode,
            st_ctime = self.ctime,
            st_atime = self.atime,
            st_mtime = self.mtime,
            st_nlink = self.nlink,
            st_size = self.get_size(),
            st_uid = self.uid,
            st_gid = self.gid,
            st_blocks = int(self.get_size() / 512)
        )

class MyFs(Operations):
    fs_name = "Myfs"
    
    def __init__(self):
        self.root_inode = Inode(
            S_IFDIR | 0o755,
            time(),
            time(),
            time(),
            getuid(),
            getgid(),
            "/"
            )
        self.name2inode = {}
        self.fd = 0

    @staticmethod
    def get_filename_and_parentdir(path):
        path_list = path.split('/')
        # need to extract the current filename and parent_dirname
        # I think there may be a more idiomatic way to do this
        curr_filename = path_list[-1]
        parent_dir = '/'.join(path_list[:len(path_list) - 1])

        return curr_filename, parent_dir
    
    # we didnt cache the filename2inode mapping.
    # Search for the filesystem hierarchy. 
    # expensive af :(
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
                if ((node.name == curr_name) and (S_IFMT(node.mode) in mode)):
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

    def invalidate_cache(self, path):
        try:
            del self.name2inode[path]    
        except KeyError:
            pass

    def chmod(self, path, mode):
        inode = self.get_inode(path, [S_IFDIR, S_IFREG])
        if inode is None:
            raise FuseOSError(ENOENT)

        inode.mode &= 0o770000 # zero out the permission bits
        inode.mode |= mode

    def chown(self, path, uid, gid):
        inode = self.get_inode(path, [S_IFDIR, S_IFREG])
        if inode is None:
            raise FuseOSError(ENOENT)

        inode.uid = uid
        inode.gid = gid
 
    def write(self, path, data, offset, fh):
        inode = self.get_inode(path, [S_IFREG])        
        if inode is None:
            raise FuseOSError(ENOENT)

        inode.data_blocks.add_data(data) 

        return len(data)

    def read(self, path, size, offset, fh):
        inode = self.get_inode(path, [S_IFREG])
        if inode is None:
            raise FuseOSError(ENOENT)

        return inode.data_blocks.get_data()

    def unlink(self, path):
        curr_filename, parent_dir = MyFs.get_filename_and_parentdir(path)

        curr_inode = self.get_inode(path, [S_IFREG])
        parent_inode = self.get_inode(parent_dir, [S_IFDIR])
        if ((parent_inode is None) or (curr_inode is None)):
            raise FuseOSError(ENOENT)

        # first check the curr_inode link count
        # delete from parent inode only if link count is 0
        curr_inode.nlink -= 1
        if curr_inode.nlink == 0:
            parent_inode.inodes.remove(curr_inode)

        self.invalidate_cache(path)

    def rename(self, old, new):
        print(old)
        print(new)
        curr_inode = self.get_inode(old, [S_IFREG, S_IFDIR])
        if curr_inode is None:
            raise FuseOSError(ENOENT)

        new_filename, parent_dir = MyFs.get_filename_and_parentdir(new)
        curr_inode.set_name(new_filename)

        self.invalidate_cache(old)

    def create(self, path, mode): 
        curr_filename, parent_dir = MyFs.get_filename_and_parentdir(path)
        
        inode = Inode(
            S_IFREG | 0o755,
            time(),
            time(),
            time(),
            getuid(),
            getgid(),
            curr_filename
            )

        parent_inode = self.get_inode(parent_dir, [S_IFDIR])
        if parent_inode is None:
            raise FuseOSError(ENOENT)

        parent_inode.inodes.append(inode)

        return 0

    def mkdir(self, path, mode):
        curr_filename, parent_dir = MyFs.get_filename_and_parentdir(path)
        
        inode = Inode(
            S_IFDIR | 0o755,
            time(),
            time(),
            time(),
            getuid(),
            getgid(),
            curr_filename
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

        self.invalidate_cache(path)

    def readdir(self, path, fh):  
        node = self.get_inode(path, [S_IFDIR, S_IFREG])
        if node is None:
            return None

        for node in node.inodes:
            yield node.name

    def getattr(self, path, fh=None):
        node = self.get_inode(path, [S_IFDIR, S_IFREG])
        if node is None:
            raise FuseOSError(ENOENT)
        
        return node.get_inode_info()
        
if __name__ == "__main__":
    mount_point = sys.argv[1]

    fuse = FUSE(MyFs(), mount_point, foreground=True, nothreads=True)

