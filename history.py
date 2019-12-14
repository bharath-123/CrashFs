import pickle
from os import mkdir, path

class CrashHistory():
    def __init__(self, backupstore):
        self.backupstore = backupstore + "/CrashFsBackups"
        CrashHistory.mkdirs(self.backupstore)

    @staticmethod
    def mkdirs(dirname):
        if not path.exists(dirname):
            mkdir(dirname)

    def add_to_history(self, state, version):
        dirname = self.backupstore + "/" + version
        filename = dirname + "/history.pkl"

        CrashHistory.mkdirs(dirname)
        
        with open(filename, "wb") as fd:
            pickle.dump(state, fd)

    def get_latest_history(self, version):
        filename = self.backupstore + "/" + version + "/history.pkl"

        if not path.exists(filename):
            return None
        
        with open(filename, "rb") as fd:
            backup = pickle.load(fd)

        return backup
