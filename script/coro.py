import sys
import types


def stack():  # running call stack, innermost first
    f, out = sys._getframe(1), []
    while f:
        out.append(f.f_code.co_name)
        f = f.f_back
    return " <- ".join(out)


def chain(c):  # suspended chain via cr_await / gi_yieldfrom
    out = []
    while c is not None:
        out.append(c.__qualname__)
        c = getattr(c, "cr_await", None) or getattr(c, "gi_yieldfrom", None)
    return " -> ".join(out)


@types.coroutine
def c5():
    print("c5 running :", stack())
    got = yield "ping"  # bare yield: goes all the way to the driver
    print("c5 resumed with", got)
    return got * 2


async def c4():
    return await c5()


async def c3():
    return await c4()


async def c2():
    return await c3()


async def c1():
    return await c2()


co = c1()
print("created    :", chain(co), "| f_back:", co.cr_frame.f_back)

v = co.send(None)  # 1st resume
print("yielded    :", v)
print("suspended  :", chain(co))
print("c1 f_back  :", co.cr_frame.f_back)

try:
    co.send(21)  # 2nd resume
except StopIteration as e:
    print("result     :", e.value, ", chain: ", chain(co))
