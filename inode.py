from stat import *
from data import *

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

    def __init__(self, mode, ctime, atime,
            mtime, uid, gid):
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


