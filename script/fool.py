from dyrel import declare, processing_queue, query, r, v


@query(r.person(v.person))
def _(person):
	print("on_person:", person)


@query(r.person(v.pers).parent(v.par))
def _(pers, par):
	print(f"{par} is the parent of {pers}")


@query(r.person("Serhii").parent(v.par))
def _(par):
	print(f"{par} is my parent")


def main():
	declare(r.person("Jack"))
	#processing_queue.exhaust()

	declare(r.person("Jim"))
	#processing_queue.exhaust()

	declare(r.person("Oliver"))
	#processing_queue.exhaust()

	print("done declaring")
	processing_queue.exhaust()
	print("exhausted")

	declare(r.person("Serhii").parent("Tanya"))
	declare(r.person("Serhii").parent("Vova"))
	declare(r.person("Ira").parent("Tanya"))
	declare(r.person("Ira").parent("Vova"))

	processing_queue.exhaust()


if __name__ == "__main__":
	main()

