from time import gmtime, strftime

def ProperTime(time):
    f = strftime('%H:%M:%S', gmtime(time)).split(":")
    h, m, s = int(f[0]), int(f[1]), int(f[2])

    res = ""
    if h == 1:
        res += "1 hour "
    elif h > 1:
        res += f"{h} hours "
    
    if m == 1:
        res += "1 minute "
    elif m > 1:
        res += f"{m} minutes "
    
    if s == 1:
        res += "1 second"
    else:
        res += f"{s} seconds"
    
    return res