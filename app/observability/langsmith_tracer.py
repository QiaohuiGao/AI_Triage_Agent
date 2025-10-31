def trace_step(step_name: str):
    def deco(func):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return deco
