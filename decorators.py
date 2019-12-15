

def logger(fn):
    def logged(*args, **kwargs):
        print("{} on path {}".format(fn.__name__, args[1]))

        return fn(*args, **kwargs)

    return logged
