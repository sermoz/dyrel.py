from collections import deque

from dyrel.util import Slotted_Class


class Processing_Queue(metaclass=Slotted_Class):
	# dirty: set
	queue: deque

	def __init__(self):
		# self.dirty = set()
		self.queue = deque()

	def add(self, observer):
		self.queue.append(observer)

	def add_all(self, observers):
		self.queue.extend(observers)

	def exhaust(self):
		while self.queue:
			observer = self.queue.popleft()
			observer.revalidate()


processing_queue = Processing_Queue()
