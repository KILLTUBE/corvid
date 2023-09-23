
# flatten an n dimensional list
def Flatten(lst: list) -> list:
    res: list = []
    for i in lst:
        if isinstance(i, list):
            res += Flatten(i)
        else:
            res.append(i)
    return res

def AddUnique(arr: list, item):
    if item not in arr:
        arr.append(item)