# This 'rpyc' subpackage is just a stripped version of the RPyC custom protocol for
# Python. See here: https://github.com/tomerfiliba-org/rpyc.
#
# Why we decided to "customize" it:
#   - we need a way to wake up a thread waiting on a socket. For example, in the Runtime
#     host process, we need to notify clients on changed file annotations. We don't want
#     to do this synchronously on the main thread.
#  - no need for complicated multithreading support (locks, queues, condition vars, etc.)
#  - no need for that much wrappers and complications.
