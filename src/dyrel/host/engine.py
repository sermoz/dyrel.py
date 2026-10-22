from .inotify import Inotify
from .inotify import Mask


async def run():
	inotify = Inotify()
	wd: int = inotify.add_watch("sample", Mask.MODIFY)
	
	async for event in inotify.events():
		print(event)

	inotify.remove_watch(wd)
	inotify.close()
