CrashFs: CrashFs is a filesystem which allows you to checkpoint multiple filesystem states and store the checkpointed states in any external storage device. These states can be restored anytime.

How to use it?

Run:
python3 fs.py <mountpoint of CrashFs> <mountpoint of external storage device>

A bunch of pseudo files will appear. 
1) store: This file is used to store the current state of the filesystem. To store, just write the name you want to give to the current state of the filesystem to the store file. The state will be saved in an external storage device specified.
eg:
Let's say we want to call the state as "state1"
echo "state1" > store will do the trick

2) restore: This file is used to restore the filesystem to a previously checkpointed state. Just echo the name of the checkpointed state to the restore file. 
eg:
Let's say we want to restore the state "state1"
echo "state1" > restore

3) versions: This directory contains 0-byte files which just display the name of the states stored in the current supplied storage devices.

Other than that, this is a pretty normal filesystem with all the basic operations Linux provides! Have fun!
