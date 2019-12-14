

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
        return len(self.file)

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


