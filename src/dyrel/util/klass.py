def member_of(klass):
    def wrapper(member):
        assert not hasattr(klass, member.__name__), (
            f'Class {klass} already has member "{member.__name__}"'
        )
        setattr(klass, member.__name__, member)
        return None

    return wrapper
