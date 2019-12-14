import pickle
from os import mkdir, path

class CrashHistory():
    def __init__(self, backupstore):
        self.backupstore = backupstore + "/CrashFsBackups"
        if not path.exists(self.backupstore):
            mkdir(self.backupstore)
        self.backupfile = self.backupstore + "/history.pkl"

    def add_to_history(self, state):
        with open(self.backupfile, "wb") as fd:
            pickle.dump(state, fd)

    def get_latest_history(self):
        if not path.exists(self.backupfile):
            return None

        with open(self.backupfile, "rb") as fd:
            backup = pickle.load(fd)

        return backup


